from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from website.models import BrandVideo, PortfolioProject, PortfolioVideo


class PublicMediaSeedTests(TestCase):
    def test_requires_confirmation_before_publication(self):
        with self.assertRaisesMessage(CommandError, "Confirma la autorización"):
            call_command("seed_public_cw_media")
        self.assertFalse(BrandVideo.objects.exists())

    def test_installs_optimized_media_without_private_originals_and_is_idempotent(self):
        with override_settings(
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            }
        ):
            call_command("seed_public_cw_media", authorization_confirmed=True, verbosity=0)

            self.assertEqual(PortfolioProject.objects.filter(is_published=True).count(), 2)
            self.assertEqual(PortfolioVideo.objects.filter(is_published=True).count(), 2)
            self.assertEqual(BrandVideo.objects.filter(is_published=True).count(), 1)
            for video in (*PortfolioVideo.objects.all(), *BrandVideo.objects.all()):
                self.assertFalse(video.original_video.name)
                for field_name in ("preview_video", "full_video", "poster_image"):
                    field = getattr(video, field_name)
                    self.assertTrue(field.name)
                    self.assertTrue(field.storage.exists(field.name))

            call_command("seed_public_cw_media", authorization_confirmed=True, verbosity=0)
            self.assertEqual(PortfolioProject.objects.count(), 2)
            self.assertEqual(PortfolioVideo.objects.count(), 2)
            self.assertEqual(BrandVideo.objects.count(), 1)
