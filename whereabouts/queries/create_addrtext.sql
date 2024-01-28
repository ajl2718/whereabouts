create table addrtext_with_detail as (
    with tokens as 
    (
        select 
        addr_id addr_id, 
        trim(regexp_replace(regexp_replace(upper(address_label), '[^A-Z0-9]+', ' ', 'g'), '  ', ' ')) addr,
        unnest(string_to_array(trim(regexp_replace(regexp_replace(upper(address_label), '[^A-Z0-9]+', ' ', 'g'), '  ', ' ')), ' ')) as token
        from addrtext
    ),
    addrtext_with_detail_pre as (
        select addr_id addr_id, addr, array_agg(token) numeric_tokens 
        from tokens
        where regexp_matches(token, '[0-9]+[A-Z]{0,1}')
        group by addr_id, addr
    )
    select t1.*, t2.address_label, t2.locality_name suburb, t2.postcode, t2.latitude, t2.longitude 
    from addrtext_with_detail_pre t1
    left join 
    addrtext t2 on t1.addr_id=t2.addr_id
);