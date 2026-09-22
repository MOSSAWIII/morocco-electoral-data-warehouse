-- V15: cinq analyses de référence issues du registre SQL canonique.

-- 1. Évolution électorale territoriale des partis
SELECT * FROM cube_party_territorial_evolution ORDER BY region_name, party_id, election_year LIMIT 10;

-- 2. Fragmentation, HHI et compétitivité
SELECT year, count(*) contests, avg(hhi) mean_hhi, avg(enp) mean_enp, avg(victory_margin_pp) mean_margin_pp FROM cube_electoral_competitiveness GROUP BY year ORDER BY year;

-- 3. Résultats versus contrôle communal
SELECT year, result_control_alignment, count(*) contests FROM cube_communal_control GROUP BY year, result_control_alignment ORDER BY year, result_control_alignment;

-- 4. Mandats et représentation territoriale
SELECT legislature, region, gender, sum(published_mandates)::BIGINT published_mandates FROM cube_mandate_representation GROUP BY legislature, region, gender ORDER BY legislature, region, gender LIMIT 25;

-- 5. Questions parlementaires publiées
SELECT * FROM cube_parliamentary_publication ORDER BY calendar_year, question_type;
