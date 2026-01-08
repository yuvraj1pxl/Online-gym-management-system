from django.core.management.base import BaseCommand
from body.models import Trainer

class Command(BaseCommand):
    help = 'Populates the database with the 6 trainers from your HTML'

    def handle(self, *args, **kwargs):
        trainers_data = [
            {
                'name': 'Aiden Cole',
                'specialization': 'Strength & Conditioning • Powerlifting',
                'bio_short': 'Elite powerlifting coach designing evidence-based strength cycles.',
                'bio_full': 'Aiden programs progressive overload cycles, technique refinement and competition peaking strategies. He brings sports science into practical sessions, focusing on bar mechanics, core integrity and maximal recovery.',
                'image_url': 'https://i.pinimg.com/736x/0c/54/5f/0c545f998244fcfc4eed34c904814c33.jpg',
                'order': 0,
            },
            {
                'name': 'Sophia Reynolds',
                'specialization': 'Functional Fitness • Mobility Specialist',
                'bio_short': 'Expert in restoring movement patterns and joint resilience.',
                'bio_full': 'Sophia blends mobility systems, corrective exercise, and dynamic strength to rebuild movement quality. She emphasizes pain-free progression, posture optimization, and sustainable performance improvements.',
                'image_url': 'https://i.pinimg.com/736x/61/75/05/6175055a98b055384d26c112dcffdc8b.jpg',
                'order': 1,
            },
            {
                'name': 'Liam Parker',
                'specialization': 'HIIT • Fat Loss Specialist',
                'bio_short': 'High-intensity programming to maximize metabolic effect.',
                'bio_full': 'Liam constructs interval and metabolic resistance sessions that optimize calorie burn and cardio-resilience. He tailors volumes to recovery status and lifestyle to keep clients progressing without burnout.',
                'image_url': 'https://i.pinimg.com/736x/c1/97/91/c197916672d7b82ae89a3ab936f84813.jpg',
                'order': 2,
            },
            {
                'name': 'Isabella Grant',
                'specialization': 'Yoga • Mind-Body Wellness',
                'bio_short': 'Yoga coach combining breathwork with functional flexibility.',
                'bio_full': 'Isabella focuses on breath-led flows, mobility blends and restorative practices to support stress resilience and functional range. Her approach ties mental clarity to durable physical progress.',
                'image_url': 'https://i.pinimg.com/736x/15/6b/08/156b08b79301df70b7f6b1ed88c37b2f.jpg',
                'order': 3,
            },
            {
                'name': 'Ethan Brooks',
                'specialization': 'Sports Performance • Speed & Agility',
                'bio_short': 'Performance coach specializing in speed, agility and power.',
                'bio_full': 'Ethan uses plyometrics, resisted sprints and restorative periodization to help athletes reach fast-twitch potential. He integrates testing, metrics and recovery for consistent, measurable gains.',
                'image_url': 'https://i.pinimg.com/736x/83/fd/bb/83fdbb28f690dd5e536352f5661adc67.jpg',
                'order': 4,
            },
            {
                'name': 'Olivia Knight',
                'specialization': 'Nutrition • Holistic Coaching',
                'bio_short': 'Nutrition specialist blending habit coaching with evidence-based plans.',
                'bio_full': 'Olivia builds tailored nutrition strategies aligned with training, sleep and lifestyle. Her coaching includes habit scaffolding and progress tracking for long-term adherence and performance.',
                'image_url': 'https://i.pinimg.com/1200x/79/0d/07/790d07267945ce8422f5f5923500c7dc.jpg',
                'order': 5,
            },
        ]

        created_count = 0
        updated_count = 0

        for data in trainers_data:
            trainer, created = Trainer.objects.update_or_create(
                name=data['name'],
                defaults={
                    'specialization': data['specialization'],
                    'bio_short': data['bio_short'],
                    'bio_full': data['bio_full'],
                    'image_url': data['image_url'],
                    'order': data['order'],
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {trainer.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Updated: {trainer.name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Done! Created: {created_count}, Updated: {updated_count}'
        ))