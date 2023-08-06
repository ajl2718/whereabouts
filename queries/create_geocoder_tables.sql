create table addrtext_pre (
addr_id varchar,
addr varchar
);

CREATE TABLE phrase -- Compute 2-word phrase tokens
(addr_id varchar not null,
tokenphrase text not null);

CREATE TABLE phraseinverted -- Compute inverted index
(tokenphrase text not null,
addr_ids varchar[] not null,
frequency bigint not null);

CREATE TABLE skipphrase -- Compute 2-word phrase tokens
(addr_id varchar not null,
tokenphrase text not null);

CREATE TABLE skipphraseinverted -- Compute inverted index
(tokenphrase text not null,
addr_ids varchar[] not null,
frequency bigint not null);

CREATE TABLE trigramphrase -- Compute 2-word trigram phrases
(addr_id varchar not null,
trigramphrase text not null
);

CREATE TABLE trigramphraseinverted -- Compute trigram inverted index
(trigramphrase text not null,
addr_ids varchar[] not null,
frequency bigint not null);

--CREATE TABLE streetabbrev
--(name text not null,
--abbrev text not null);