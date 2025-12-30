create table tg_distinct as (
    with tg_distinct_pre as (
        select distinct(trigramphrase) trigramphrase from
        trigramphraseinverted
    )
    select trigramphrase, row_number() over () row_num
    from tg_distinct_pre
);

create table trigramphraseinverted2 as (
    select t1.*, t2.row_num
    from trigramphraseinverted t1
    left join tg_distinct t2
    on t1.trigramphrase=t2.trigramphrase
);

CREATE TABLE trigramphraseinverted3(
    trigramphrase integer not null,
    addr_ids integer[] not null,
    frequency bigint not null
);