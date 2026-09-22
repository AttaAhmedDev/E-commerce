class TestCheckoutConcurrency:
    @pytest.mark.django_db(transaction=True)
    def test_concurrent_checkouts_cannot_oversell_last_unit(self):
        """
        The critical test: two users simultaneously checking out the
        LAST unit of a variant. Without select_for_update(), both
        requests could read quantity=1 before either commits, and
        both would succeed — overselling by one unit. With proper
        locking, exactly one should succeed and the other should be
        rejected.
        """
        user_a = UserFactory(email="race_a@example.com", password="Pass123")
        user_b = UserFactory(email="race_b@example.com", password="Pass123")
        variant = ProductVariantFactory(
            price=Decimal("50.00"), inventory=1
        )  # only 1 in stock!

        address_a = _address_payload(user_a)
        address_b = _address_payload(user_b)

        cart_a = Cart.objects.create(user=user_a)
        CartItem.objects.create(cart=cart_a, variant=variant, quantity=1)
        cart_b = Cart.objects.create(user=user_b)
        CartItem.objects.create(cart=cart_b, variant=variant, quantity=1)

        results = {}

        def checkout(user, address, key):
            client = APIClient()
            client.force_authenticate(user=user)
            response = client.post(
                "/api/v1/orders/checkout/",
                {
                    "shipping_address_id": address.id,
                    "billing_address_id": address.id,
                    "payment_method": "cod",
                },
            )
            results[key] = response.status_code
            connection.close()  # each thread needs its own DB connection cleanup

        thread_a = threading.Thread(target=checkout, args=(user_a, address_a, "a"))
        thread_b = threading.Thread(target=checkout, args=(user_b, address_b, "b"))

        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        # Exactly ONE should have succeeded (201), the other rejected (400)
        statuses = sorted(results.values())
        assert statuses == [400, 201]

        # Final stock must be exactly 0 — never negative, never both orders fulfilled
        variant.refresh_from_db()
        assert variant.inventory.quantity == 0
        assert Order.objects.count() == 1
