create table addrtext_with_numerics as (
    with tokens as 
    (
        select 
        addr_id, 
        trim(regexp_replace(regexp_replace(upper(addr), '[^A-Z0-9]+', ' '), '  ', ' ')) address,
        unnest(string_to_array(trim(regexp_replace(regexp_replace(upper(addr), '[^A-Z0-9]+', ' '), '  ', ' ')), ' ')) as token
        from addrtext
    )
    select addr_id address_id, address, array_agg(token) numeric_tokens 
    from tokens
    where regexp_matches(token, '[0-9]+')
    group by address_id, address
);