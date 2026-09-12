from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="morocco_elections", description="Warehouse électoral marocain")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Construire un export du warehouse")
    build.add_argument("version", choices=("v9", "v10", "v11", "v12", "v13"))
    build.add_argument("--data-dir")

    export = commands.add_parser("export", help="Produire un paquet de diffusion ouvert")
    export.add_argument("version", choices=("v13", "v14"))
    export.add_argument("--data-dir")
    export.add_argument("--output-dir")
    export.add_argument("--manifest-output")
    export.add_argument("--readme-output")

    analyze = commands.add_parser("analyze", help="Exécuter les analyses de référence d'une release validée")
    analyze.add_argument("version", choices=("v11", "v12", "v13"))
    analyze.add_argument("--data-dir")
    analyze.add_argument("--format", choices=("text", "json"), default="text")

    validate = commands.add_parser("validate", help="Valider le dépôt et les données locales")
    validate.add_argument("--mode", choices=("ci", "full"), default="ci")
    validate.add_argument("--data-dir")
    validate.add_argument("--release", choices=("v9", "v10", "v11", "v12", "v13", "v14", "all"), default="v14")
    validate.add_argument("--baseline", choices=("v9", "v10", "v11", "v12", "v13"))

    sources = commands.add_parser("sources", help="Cataloguer et acquérir des sources sans les ingérer")
    source_commands = sources.add_subparsers(dest="source_command", required=True)
    catalog = source_commands.add_parser("catalog", help="Valider et résumer le catalogue d'acquisition")
    catalog.add_argument("--catalog")
    inventory = source_commands.add_parser("inventory", help="Consolider les profils RAW dans un inventaire partageable")
    inventory.add_argument("--as-of", required=True)
    inventory.add_argument("--data-dir")
    inventory.add_argument("--output")
    acquire = source_commands.add_parser("acquire", help="Conserver et profiler une source dans les RAW immuables")
    acquire.add_argument("--source-id", required=True)
    source_input = acquire.add_mutually_exclusive_group(required=True)
    source_input.add_argument("--url")
    source_input.add_argument("--input")
    acquire.add_argument("--filename")
    acquire.add_argument("--as-of")
    acquire.add_argument("--data-dir")
    acquire.add_argument("--catalog")
    electoral_profile = source_commands.add_parser(
        "profile-electoral-archives", help="Profiler les sept archives électorales acquises pour V13"
    )
    electoral_profile.add_argument("--baseline", choices=("v12",), default="v12")
    electoral_profile.add_argument("--as-of", required=True)
    electoral_profile.add_argument("--data-dir")
    electoral_profile.add_argument("--output")
    electoral_profile.add_argument("--report-output")

    docs = commands.add_parser("docs", help="Historique: générer la documentation d'une release")
    docs.add_argument("version", choices=("v9", "v10", "v11", "v12", "v13"))
    docs.add_argument("--data-dir")

    qualify = commands.add_parser("qualify", help="Historique: reproduire une qualification de source")
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
    parliament = qualification.add_parser("parliament", help="Qualifier les questions parlementaires écrites")
    parliament.add_argument("--candidate", action="append", dest="candidates")
    parliament.add_argument("--baseline", choices=("v11",), default="v11")
    parliament.add_argument("--as-of", default="2026-09-09")
    parliament.add_argument("--output")
    parliament.add_argument("--data-dir")
    electoral = qualification.add_parser(
        "electoral-archives", help="Qualifier en bloc les archives électorales profilées pour V13"
    )
    electoral.add_argument("--baseline", choices=("v12",), default="v12")
    electoral.add_argument("--as-of", required=True)
    electoral.add_argument("--output")
    electoral.add_argument("--report-output")

    quality = commands.add_parser("quality", help="Historique: reproduire une baseline qualité")
    quality_commands = quality.add_subparsers(dest="quality_command", required=True)
    baseline = quality_commands.add_parser("baseline", help="Générer la baseline V10-QA")
    baseline.add_argument("--release", choices=("v10", "v11"), default="v10")
    baseline.add_argument("--as-of")
    baseline.add_argument("--data-dir")
    baseline.add_argument("--metadata-output")
    baseline.add_argument("--report-output")

    identity = commands.add_parser("identity", help="Historique: reproduire un registre d'identités")
    identity_commands = identity.add_subparsers(dest="identity_command", required=True)
    registry = identity_commands.add_parser("build-registry", help="Construire le registre électoral V13")
    registry.add_argument("--baseline", choices=("v12",), default="v12")
    registry.add_argument("--as-of", required=True)
    registry.add_argument("--data-dir")
    registry.add_argument("--output")
    registry.add_argument("--report-output")

    github = commands.add_parser("github", help="Historique: republier le backlog initial")
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
        elif args.version == "v11":
            from morocco_elections.releases.v11.build import main as build_release
        elif args.version == "v12":
            from morocco_elections.releases.v12.build import main as build_release
        else:
            from morocco_elections.releases.v13.build import main as build_release
        build_release(data_dir=args.data_dir)
        return 0
    if args.command == "docs":
        if args.version == "v9":
            from morocco_elections.legacy.v9.documentation import main as generate_docs
        elif args.version == "v10":
            from morocco_elections.releases.v10.documentation import main as generate_docs
        elif args.version == "v11":
            from morocco_elections.releases.v11.documentation import main as generate_docs
        elif args.version == "v12":
            from morocco_elections.releases.v12.documentation import main as generate_docs
        else:
            from morocco_elections.releases.v13.documentation import main as generate_docs
        generate_docs(data_dir=args.data_dir)
        return 0
    if args.command == "validate":
        from morocco_elections.quality.validation import report

        return report(mode=args.mode, data_dir=args.data_dir, release=args.release, baseline=args.baseline)
    if args.command == "analyze" and args.version == "v11":
        from morocco_elections.analysis.v11 import run

        return run(data_dir=args.data_dir, output_format=args.format)
    if args.command == "analyze" and args.version == "v12":
        from morocco_elections.analysis.v12 import run

        return run(data_dir=args.data_dir, output_format=args.format)
    if args.command == "analyze" and args.version == "v13":
        from morocco_elections.analysis.v13 import run

        return run(data_dir=args.data_dir, output_format=args.format)
    if args.command == "export" and args.version == "v13":
        from morocco_elections.exports.open_v13 import run

        return run(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            manifest_output=args.manifest_output,
            readme_output=args.readme_output,
        )
    if args.command == "export" and args.version == "v14":
        from morocco_elections.exports.open_v14 import run

        return run(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            manifest_output=args.manifest_output,
            readme_output=args.readme_output,
        )
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
    if args.command == "qualify" and args.qualification == "parliament":
        from morocco_elections.research.parliamentary_questions import qualify

        return qualify(
            candidates=args.candidates,
            baseline=args.baseline,
            as_of=args.as_of,
            output=args.output,
            data_dir=args.data_dir,
        )
    if args.command == "qualify" and args.qualification == "electoral-archives":
        from morocco_elections.research.electoral_qualification import generate

        return generate(
            as_of=args.as_of,
            baseline=args.baseline,
            output=args.output,
            report_output=args.report_output,
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
    if args.command == "identity" and args.identity_command == "build-registry":
        from morocco_elections.domains.identity.registry import generate

        return generate(
            data_dir=args.data_dir,
            as_of=args.as_of,
            baseline=args.baseline,
            output=args.output,
            report_output=args.report_output,
        )
    if args.command == "github" and args.github_command == "publish-backlog":
        from morocco_elections.github.backlog import publish

        return publish(repo=args.repo, dry_run=args.dry_run)
    if args.command == "sources" and args.source_command == "catalog":
        from morocco_elections.sources.acquisition import catalog_summary

        return catalog_summary(catalog_path=args.catalog)
    if args.command == "sources" and args.source_command == "inventory":
        from morocco_elections.sources.acquisition import generate_inventory

        return generate_inventory(data_dir=args.data_dir, as_of=args.as_of, output=args.output)
    if args.command == "sources" and args.source_command == "acquire":
        from morocco_elections.sources.acquisition import acquire

        return acquire(
            source_id=args.source_id,
            url=args.url,
            input_path=args.input,
            filename=args.filename,
            as_of=args.as_of,
            data_dir=args.data_dir,
            catalog_path=args.catalog,
        )
    if args.command == "sources" and args.source_command == "profile-electoral-archives":
        from morocco_elections.research.electoral_archives import generate

        return generate(
            data_dir=args.data_dir,
            as_of=args.as_of,
            baseline=args.baseline,
            output=args.output,
            report_output=args.report_output,
        )
    raise AssertionError("Commande non gérée")
