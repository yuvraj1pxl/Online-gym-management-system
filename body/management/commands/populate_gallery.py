from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from body.models import GalleryImage
import os

class Command(BaseCommand):
    help = 'Populate gallery images from static files'

    def handle(self, *args, **options):
        # Gallery data with image/video filenames and titles
        gallery_data = [
            {'title': 'Gym Setup 2', 'image': 'img2.jpeg'},
            {'title': 'Gym Setup 3', 'image': 'img3.png'},
            {'title': 'Gym Setup 4', 'image': 'img4.png'},
            {'title': 'Instagram', 'image': 'insta.png'},
            {'title': 'LinkedIn', 'image': 'linkedin.png'},
            {'title': 'YouTube', 'image': 'youtube.png'},
            {'title': 'Form Guide', 'image': 'form_bg.mp4'},
            {'title': 'Gym Background', 'image': 'gym_bg.mp4'},
            {'title': 'Training Video', 'image': 'video.mp4'},
            {'title': 'Workout Video 2', 'image': 'video2.mp4'},
            {'title': 'Workout Video 3', 'image': 'video3.mp4'},
        ]

        for item in gallery_data:
            # Check if image already exists
            if GalleryImage.objects.filter(title=item['title']).exists():
                self.stdout.write(f"✓ {item['title']} already exists, skipping...")
                continue

            try:
                # Path to the image/video file
                if item['image'].endswith(('.mp4', '.avi', '.mov')):
                    file_path = f'body/video/{item["image"]}'
                else:
                    file_path = f'body/img/{item["image"]}'
                
                # Create GalleryImage object
                gallery = GalleryImage(title=item['title'])
                
                # Save the file path
                gallery.image = file_path
                gallery.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Added: {item['title']}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error adding {item['title']}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS('\n✓ Gallery population complete!')
        )