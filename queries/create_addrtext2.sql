insert into addrtext_pre
with address_detail_with_row_num as (
    select 
    *,
    row_number() over () row_num
    from address_view where address_view.state_abbreviation == $1
),
address_detail_subset as (
    select * from address_detail_with_row_num
    where row_num % 10 == $2
)
select
address_detail_pid as addr_id,
(
    trim(regexp_replace
    (
        ifnull(cast(lot_number_prefix as text), '') || '' ||
        ifnull(cast(lot_number as text), '') || '' ||
        ifnull(cast(lot_number_suffix as text), '') || ' ' ||
        ifnull(flat_type, '') || ' ' ||
        ifnull(cast(flat_number_prefix as text), '') || '' ||
        ifnull(cast(flat_number as text), '') || '' ||
        ifnull(cast(flat_number_suffix as text), '') || ' ' ||
        ifnull(level_type, '') || ' ' ||
        ifnull(cast(level_number_prefix as text), '') || '' ||
        ifnull(cast(level_number as text), '') || '' ||
        ifnull(cast(level_number_suffix as text), '') || ' ' ||
        ifnull(cast(number_first_prefix as text), '') || '' ||
        ifnull(cast(number_first as text), '') || '' ||
        ifnull(cast(number_first_suffix as text), '') || ' ' ||
        ifnull(cast(number_last_prefix as text), '') || '' ||
        ifnull(cast(number_last as text), '') || '' ||
        ifnull(cast(number_last_suffix as text), '') || ' ' ||
        ifnull(street_name, '') || ' ' ||
        ifnull(street_type_code, '') || ' ' ||
        ifnull(locality_name, '') || ' ' ||
        ifnull(street_suffix_type, '') || ' ' ||
        ifnull(state_abbreviation, '') || ' ' ||
        ifnull(cast(postcode as text), ''),
        '[\s]+', ' ', 'g')
    )
) addr
from address_detail_subset;