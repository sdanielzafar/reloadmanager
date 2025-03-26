from reloadmanager.arcion.nxp_config_builder import NxpConfigBuilder
from reloadmanager.arcion.replicant_runner import ReplicantRunner


def main(args):
    builder: NxpConfigBuilder = NxpConfigBuilder(
        source_table=args.source_table,
        target_table=args.target_table,
        extractor_threads=args.threads,
        config_dir_path=args.config_dir_path
    )

    reloader: ReplicantRunner = ReplicantRunner(
        builder=builder,
        replicant_path=args.replicant_path
    )

    reloader.run_snapshot()
