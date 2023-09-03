create unique index addrtext_addr_id_idx on addrtext_with_detail(addr_id);

create index phraseinverted_tokenphrase_idx on phraseinverted(tokenphrase);

--create index phrase_tokenphrase_idx on phrase(tokenphrase);

--create index phrase_addr_id_idx on phrase(addr_id);

--create unique index address_default_geocode_address_detail_pid_idx on address_default_geocode(address_detail_pid);