from django.core.management.base import BaseCommand
from core.services.tracking_service import EmotionTrackingService


class Command(BaseCommand):
    help = "Runs real-time camera emotion tracking service with pgvector face recognition"

    def add_arguments(self, parser):
        parser.add_argument(
            '--camera',
            type=int,
            default=0,
            help='Camera device index (default: 0)'
        )

        parser.add_argument(
            '--no-window',
            action='store_true',
            help='Disable OpenCV display window'
        )

    def handle(self, *args, **options):
        camera_index = options.get('camera', 0)
        show_window = not options.get('no_window', False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Emotion Tracking Service | camera={camera_index} | window={show_window}"
            )
        )

        service = EmotionTrackingService(
            camera_index=camera_index,
            show_window=show_window
        )

        try:
            service.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Stopping service (KeyboardInterrupt)..."))
            service.shutdown()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Service crashed: {str(e)}"))
            service.shutdown()
            raise

        self.stdout.write(self.style.SUCCESS("Service stopped cleanly"))