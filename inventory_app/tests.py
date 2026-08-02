from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationFlowTests(TestCase):
    def test_signup_creates_superuser_and_redirects_to_login(self):
        response = self.client.post(
            reverse("signup"),
            {
                "name": "Test User",
                "email": "test@example.com",
                "business_name": "Example Business",
                "mobile_number": "9876543210",
                "password": "strongpass123",
                "repeat_password": "strongpass123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))

        user = get_user_model().objects.get(email="test@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.username, "test@example.com")

    def test_login_redirects_superuser_to_dashboard(self):
        user = get_user_model().objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="strongpass123",
            first_name="Admin",
        )
        user.is_superuser = True
        user.is_staff = True
        user.save()

        response = self.client.post(
            reverse("login"),
            {"email": "admin@example.com", "password": "strongpass123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("home"))
