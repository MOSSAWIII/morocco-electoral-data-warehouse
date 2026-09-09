from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="morocco_elections", description="Warehouse électoral marocain")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Construire un export du warehouse")
    build.add_argument("version", choices=("v9", "v10", "v11"))
    build.add_argument("--data-dir")

    docs = commands.add_parser("docs", help="Générer la documentation")
    docs.add_argument("version", choices=("v9", "v10", "v11"))
    docs.add_argument("--data-dir")

    validate = commands.add_parser("validate", help="Valider le dépôt et les données locales")
    validate.add_argument("--mode", choices=("ci", "full"), default="ci")
    validate.add_argument("--data-dir")
    validate.add_argument("--release", choices=("v9", "v10", "v11", "all"), default="all")
    validate.add_argument("--baseline", choices=("v9", "v10"))

    analyze = commands.add_parser("analyze", help="Exécuter les analyses de référence d'une release validée")
    analyze.add_argument("version", choices=("v11",))
    analyze.add_argument("--data-dir")
    analyze.add_argument("--format", choices=("text", "json"), default="text")

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
    denominators = qualification.add_parser(
        "electoral-denominators", help="Qualifier les inscrits communaux 2015 et 2021"
    )
    denominators.add_argument("--candidate-2015")
    denominators.add_argument("--candidate-2021")
    denominators.add_argument("--baseline", choices=("v10",), default="v10")
    denominators.add_argument("--as-of")
    denominators.add_argument("--data-dir")
    denominators.add_argument("--metadata-output")
    denominators.add_argument("--decision-output")
    presidencies = qualification.add_parser(
        "local-presidencies", help="Qualifier les 135 présidences communales 2021 non résolues"
    )
    presidencies.add_argument("--evidence-index")
    presidencies.add_argument("--baseline", choices=("v10",), default="v10")
    presidencies.add_argument("--as-of")
    presidencies.add_argument("--data-dir")
    presidencies.add_argument("--metadata-output")
    presidencies.add_argument("--decision-output")
    hcp = qualification.add_parser("hcp-indicators", help="Qualifier les indicateurs communaux HCP 2014 et 2024")
    hcp.add_argument("--candidate-2014-individuals")
    hcp.add_argument("--candidate-2014-households")
    hcp.add_argument("--candidate-2024-indicators")
    hcp.add_argument("--baseline", choices=("v10",), default="v10")
    hcp.add_argument("--as-of")
    hcp.add_argument("--data-dir")
    hcp.add_argument("--metadata-output")
    hcp.add_argument("--decision-output")

    quality = commands.add_parser("quality", help="Produire des artefacts de qualité transversaux")
    quality_commands = quality.add_subparsers(dest="quality_command", required=True)
    baseline = quality_commands.add_parser("baseline", help="Générer la baseline V10-QA")
    baseline.add_argument("--release", choices=("v10", "v11"), default="v10")
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
        elif args.version == "v10":
            from morocco_elections.releases.v10.build import main as build_release
        else:
            from morocco_elections.releases.v11.build import main as build_release
        build_release(data_dir=args.data_dir)
        return 0
    if args.command == "docs":
        if args.version == "v9":
            from morocco_elections.legacy.v9.documentation import main as generate_docs
        elif args.version == "v10":
            from morocco_elections.releases.v10.documentation import main as generate_docs
        else:
            from morocco_elections.releases.v11.documentation import main as generate_docs
        generate_docs(data_dir=args.data_dir)
        return 0
    if args.command == "validate":
        from morocco_elections.quality.validation import report

        return report(mode=args.mode, data_dir=args.data_dir, release=args.release, baseline=args.baseline)
    if args.command == "analyze" and args.version == "v11":
        from morocco_elections.analysis.v11 import run

        return run(data_dir=args.data_dir, output_format=args.format)
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
    if args.command == "qualify" and args.qualification == "electoral-denominators":
        from morocco_elections.research.electoral_denominators import qualify

        return qualify(
            candidate_2015=args.candidate_2015,
            candidate_2021=args.candidate_2021,
            baseline=args.baseline,
            as_of=args.as_of,
            metadata_output=args.metadata_output,
            decision_output=args.decision_output,
            data_dir=args.data_dir,
        )
    if args.command == "qualify" and args.qualification == "local-presidencies":
        from morocco_elections.research.local_presidencies import qualify

        return qualify(
            evidence_index=args.evidence_index,
            baseline=args.baseline,
            as_of=args.as_of,
            metadata_output=args.metadata_output,
            decision_output=args.decision_output,
            data_dir=args.data_dir,
        )
    if args.command == "qualify" and args.qualification == "hcp-indicators":
        from morocco_elections.research.hcp_indicators import qualify

        return qualify(
            candidate_2014_individuals=args.candidate_2014_individuals,
            candidate_2014_households=args.candidate_2014_households,
            candidate_2024_indicators=args.candidate_2024_indicators,
            baseline=args.baseline,
            as_of=args.as_of,
            metadata_output=args.metadata_output,
            decision_output=args.decision_output,
            data_dir=args.data_dir,
        )
    if args.command == "quality" and args.quality_command == "baseline":
        from morocco_elections.quality.baseline import generate

        return generate(
            release=args.release,
            data_dir=args.data_dir,
            as_of=args.as_of,
            metadata_output=args.metadata_output,
            report_output=args.report_output,
        )
    if args.command == "github" and args.github_command == "publish-backlog":
        from morocco_elections.github.backlog import publish

        return publish(repo=args.repo, dry_run=args.dry_run)
    raise AssertionError("Commande non gérée")
