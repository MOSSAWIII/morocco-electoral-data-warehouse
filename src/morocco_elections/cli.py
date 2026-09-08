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

    qualify = commands.add_parser("qualify", help="Qualifier une source candidate sans l'ingérer")
    qualification = qualify.add_subparsers(dest="qualification", required=True)
    councils = qualification.add_parser("councils-2015", help="Qualifier les conseils communaux de 2015")
    councils.add_argument("--candidate", required=True)
    councils.add_argument("--baseline", choices=("v10",), default="v10")
    councils.add_argument("--data-dir")
    councils.add_argument("--metadata-output")
    councils.add_argument("--decision-output")
    smiig = qualification.add_parser("smiig", help="Qualifier une source SMIIG sans l'ingérer")
    smiig.add_argument("--candidate", required=True)
    smiig.add_argument("--baseline", choices=("v10",), default="v10")
    smiig.add_argument("--data-dir")
    smiig.add_argument("--metadata-output")
    smiig.add_argument("--decision-output")

    quality = commands.add_parser("quality", help="Produire des artefacts de qualité transversaux")
    quality_commands = quality.add_subparsers(dest="quality_command", required=True)
    baseline = quality_commands.add_parser("baseline", help="Générer la baseline V10-QA")
    baseline.add_argument("--release", choices=("v10",), default="v10")
    baseline.add_argument("--as-of")
    baseline.add_argument("--data-dir")
    baseline.add_argument("--metadata-output")
    baseline.add_argument("--report-output")

    github = commands.add_parser("github", help="Opérations GitHub différées")
    github_commands = github.add_subparsers(dest="github_command", required=True)
    backlog = github_commands.add_parser("publish-backlog", help="Publier les jalons et issues")
    backlog.add_argument("--repo")
    backlog.add_argument("--dry-run", action="store_true")
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
    if args.command == "qualify" and args.qualification == "councils-2015":
        from morocco_elections.research.councils_2015 import qualify_candidate

        return qualify_candidate(
            candidate=args.candidate,
            baseline=args.baseline,
            metadata_output=args.metadata_output,
            decision_output=args.decision_output,
            data_dir=args.data_dir,
        )
    if args.command == "qualify" and args.qualification == "smiig":
        from morocco_elections.research.smiig import qualify_candidate

        return qualify_candidate(
            candidate=args.candidate,
            baseline=args.baseline,
            metadata_output=args.metadata_output,
            decision_output=args.decision_output,
            data_dir=args.data_dir,
        )
    if args.command == "quality" and args.quality_command == "baseline":
        from morocco_elections.quality.baseline import generate

        return generate(
            data_dir=args.data_dir,
            as_of=args.as_of,
            metadata_output=args.metadata_output,
            report_output=args.report_output,
        )
    if args.command == "github" and args.github_command == "publish-backlog":
        from morocco_elections.github.backlog import publish

        return publish(repo=args.repo, dry_run=args.dry_run)
    raise AssertionError("Commande non gérée")
