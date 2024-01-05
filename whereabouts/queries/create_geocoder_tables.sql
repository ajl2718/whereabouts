CREATE TABLE addrtext(
    addr_id integer not null,
    ADDRESS_LABEL varchar,
    ADDRESS_SITE_NAME varchar,
    LOCALITY_NAME varchar,
    POSTCODE int,
    STATE varchar,
    LATITUDE float,
    LONGITUDE float
);

CREATE TABLE phrase -- Compute 2-word phrase tokens
(addr_id integer not null,
tokenphrase text not null);

CREATE TABLE phraseinverted -- Compute inverted index
(tokenphrase text not null,
addr_ids integer[] not null,
frequency bigint not null);

CREATE TABLE skipphrase -- Compute 2-word phrase tokens
(addr_id integer not null,
tokenphrase text not null);

CREATE TABLE skipphraseinverted -- Compute inverted index
(tokenphrase text not null,
addr_ids integer[] not null,
frequency bigint not null);

CREATE TABLE trigramphrase -- Compute 2-word trigram phrases
(addr_id integer not null,
trigramphrase text not null
);

CREATE TABLE trigramphraseinverted -- Compute trigram inverted index
(trigramphrase integer not null,
addr_ids integer[] not null,
frequency integer not null);

create table numbers as (
values
(1),
(2),
(3),
(4),
(5),
(6),
(7)
)