from reloadmanager.nxp_reload_runner import NxpReloadRunner


def main(args):
    reloader: NxpReloadRunner = NxpReloadRunner(
        args.source_table,
        args.target_table,
        args.replicant_path,
        args.config_dir_path
    )

    reloader.run_snapshot()