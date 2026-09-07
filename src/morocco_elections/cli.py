from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="morocco_elections", description="Warehouse électoral marocain")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Construire un export du warehouse")
    build.add_argument("version", choices=("v9", "v10"))
    build.add_argument("--data-dir")

    docs = commands.add_parser("docs", help="Générer la documentation")
    docs.add_argument("version", choices=("v9", "v10"))
    docs.add_argument("--data-dir")

    validate = commands.add_parser("validate", help="Valider le dépôt et les données locales")
    validate.add_argument("--mode", choices=("ci", "full"), default="ci")
    validate.add_argument("--data-dir")
    validate.add_argument("--release", choices=("v9", "v10", "all"), default="all")
    validate.add_argument("--baseline", choices=("v9",))

    github = commands.add_parser("github", help="Opérations GitHub différées")
    github_commands = github.add_subparsers(dest="github_command", required=True)
    backlog = github_commands.add_parser("publish-backlog", help="Publier les jalons et issues")
    backlog.add_argument("--repo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        if args.version == "v9":
            from morocco_elections.legacy.v9.build import main as build_release
        else:
            from morocco_elections.releases.v10.build import main as build_release
        build_release(data_dir=args.data_dir)
        return 0
    if args.command == "docs":
        if args.version == "v9":
            from morocco_elections.legacy.v9.documentation import main as generate_docs
        else:
            from morocco_elections.releases.v10.documentation import main as generate_docs
        generate_docs(data_dir=args.data_dir)
        return 0
    if args.command == "validate":
        from morocco_elections.quality.validation import report

        return report(mode=args.mode, data_dir=args.data_dir, release=args.release, baseline=args.baseline)
    if args.command == "github" and args.github_command == "publish-backlog":
        from morocco_elections.github.backlog import publish

        return publish(repo=args.repo)
    raise AssertionError("Commande non gérée")
