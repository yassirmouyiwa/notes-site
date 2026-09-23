-- =============================================================================
-- Formation DBA PostgreSQL — Jeu de données « banque »
-- Usage : sudo -u postgres psql < scripts/sql/01_jeu_de_donnees_banque.sql
--
-- Crée une base bancaire fictive :
--   bank.agences      6 lignes
--   bank.clients      :nb_clients lignes           (défaut 100 000)
--   bank.comptes      ≈ 1,5 × :nb_clients lignes
--   bank.operations   :nb_operations lignes        (défaut 2 000 000)
--
-- Volontairement, AUCUN index n'est créé sur les clés étrangères :
-- c'est l'objet d'un exercice du module 07.
-- Toutes les données sont fictives.
-- =============================================================================

\set ON_ERROR_STOP on
\set nb_clients 100000
\set nb_operations 2000000

\echo '>>> (Re)création de la base banque'
DROP DATABASE IF EXISTS banque;
CREATE DATABASE banque;
\c banque

CREATE SCHEMA bank;
SET search_path = bank, public;

-- -----------------------------------------------------------------------------
-- Tables
-- -----------------------------------------------------------------------------
CREATE TABLE bank.agences (
    id_agence   smallint PRIMARY KEY,
    ville       text NOT NULL,
    region      text NOT NULL
);

CREATE TABLE bank.clients (
    id_client       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom             text NOT NULL,
    prenom          text NOT NULL,
    cin             text NOT NULL UNIQUE,
    email           text,
    telephone       text,
    date_naissance  date,
    id_agence       smallint NOT NULL REFERENCES bank.agences,
    cree_le         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bank.comptes (
    id_compte    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_client    bigint NOT NULL REFERENCES bank.clients,
    type_compte  text NOT NULL CHECK (type_compte IN ('COURANT', 'EPARGNE', 'PRO')),
    solde        numeric(14,2) NOT NULL DEFAULT 0,
    ouvert_le    date NOT NULL DEFAULT current_date,
    statut       text NOT NULL DEFAULT 'ACTIF' CHECK (statut IN ('ACTIF', 'BLOQUE', 'CLOS'))
);

CREATE TABLE bank.operations (
    id_operation  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_compte     bigint NOT NULL REFERENCES bank.comptes,
    type_op       text NOT NULL CHECK (type_op IN ('DEPOT', 'RETRAIT', 'VIREMENT_IN', 'VIREMENT_OUT', 'PAIEMENT_CB')),
    montant       numeric(12,2) NOT NULL CHECK (montant > 0),
    date_op       timestamptz NOT NULL,
    libelle       text
);

COMMENT ON TABLE bank.clients    IS 'Clients de la banque (données personnelles : CIN, e-mail, téléphone)';
COMMENT ON TABLE bank.operations IS 'Historique des opérations bancaires';

-- -----------------------------------------------------------------------------
-- Données
-- -----------------------------------------------------------------------------
\echo '>>> Agences'
INSERT INTO bank.agences VALUES
    (1, 'Tétouan',    'Tanger-Tétouan-Al Hoceïma'),
    (2, 'Tanger',     'Tanger-Tétouan-Al Hoceïma'),
    (3, 'Rabat',      'Rabat-Salé-Kénitra'),
    (4, 'Casablanca', 'Casablanca-Settat'),
    (5, 'Fès',        'Fès-Meknès'),
    (6, 'Marrakech',  'Marrakech-Safi');

\echo '>>> Clients'
INSERT INTO bank.clients (nom, prenom, cin, email, telephone, date_naissance, id_agence)
SELECT
    (ARRAY['Alaoui','Bennani','El Idrissi','Tazi','Berrada',
           'Chraibi','Fassi','Amrani','Naciri','Ouazzani'])[1 + floor(random() * 10)::int],
    (ARRAY['Youssef','Fatima','Mohamed','Khadija','Omar',
           'Salma','Hamza','Imane','Mehdi','Sara'])[1 + floor(random() * 10)::int],
    'CIN' || lpad(g::text, 8, '0'),
    'client' || g || '@exemple.ma',
    '06' || lpad(floor(random() * 100000000)::bigint::text, 8, '0'),
    date '1950-01-01' + floor(random() * 20000)::int,
    1 + floor(random() * 6)::int
FROM generate_series(1, :nb_clients) AS g;

\echo '>>> Comptes'
INSERT INTO bank.comptes (id_client, type_compte, solde, ouvert_le)
SELECT id_client, 'COURANT',
       round((random() * 50000)::numeric, 2),
       date '2010-01-01' + floor(random() * 5000)::int
FROM bank.clients;

INSERT INTO bank.comptes (id_client, type_compte, solde, ouvert_le)
SELECT id_client, 'EPARGNE',
       round((random() * 200000)::numeric, 2),
       date '2010-01-01' + floor(random() * 5000)::int
FROM bank.clients
WHERE random() < 0.5;

-- Quelques comptes bloqués (utile pour les index partiels du module 07)
UPDATE bank.comptes SET statut = 'BLOQUE' WHERE random() < 0.01;

\echo '>>> Opérations (patience, 1 à 3 minutes)'
INSERT INTO bank.operations (id_compte, type_op, montant, date_op, libelle)
SELECT
    1 + floor(random() * (SELECT max(id_compte) FROM bank.comptes))::bigint,
    (ARRAY['DEPOT','RETRAIT','VIREMENT_IN','VIREMENT_OUT','PAIEMENT_CB'])[1 + floor(random() * 5)::int],
    round((1 + random() * 5000)::numeric, 2),
    timestamptz '2023-01-01 00:00:00+00' + random() * interval '1000 days',
    'Opération n°' || g
FROM generate_series(1, :nb_operations) AS g;

-- -----------------------------------------------------------------------------
-- Table utilisée au module 05 (anomalie « write skew »)
-- -----------------------------------------------------------------------------
CREATE TABLE bank.gardes (
    medecin    text PRIMARY KEY,
    de_garde   boolean NOT NULL
);
INSERT INTO bank.gardes VALUES ('Amina', true), ('Karim', true);

\echo '>>> VACUUM ANALYZE'
VACUUM ANALYZE;

\echo '>>> Terminé'
SELECT 'agences' AS table_, count(*) FROM bank.agences
UNION ALL SELECT 'clients',    count(*) FROM bank.clients
UNION ALL SELECT 'comptes',    count(*) FROM bank.comptes
UNION ALL SELECT 'operations', count(*) FROM bank.operations;

SELECT pg_size_pretty(pg_database_size('banque')) AS taille_base;
