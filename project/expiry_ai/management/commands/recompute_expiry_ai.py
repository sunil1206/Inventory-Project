from django.core.management.base import BaseCommand

from expiry_ai.engine import recompute_batch_signatures, recompute_all_store_recommendations


class Command(BaseCommand):
    help = "Recompute expiry AI batch intelligence + store recommendations."

    def add_arguments(self, parser):
        parser.add_argument("--alpha", type=float, default=0.8)
        parser.add_argument("--chunk", type=int, default=5000)
        parser.add_argument("--horizon", type=int, default=14)
        parser.add_argument("--min-confidence", type=float, default=0.50)
        parser.add_argument("--min-risk", type=float, default=0.35)

    def handle(self, *args, **opts):
        n_sig = recompute_batch_signatures(alpha=opts["alpha"], chunk_size=opts["chunk"])
        n_rec = recompute_all_store_recommendations(
            horizon_days=opts["horizon"],
            min_confidence=opts["min_confidence"],
            min_risk=opts["min_risk"],
        )

        self.stdout.write(self.style.SUCCESS(f"BatchSignature updated: {n_sig}"))
        self.stdout.write(self.style.SUCCESS(f"Store recommendations updated: {n_rec}"))
