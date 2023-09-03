INSERT INTO phraseinverted
SELECT tokenphrase,array_agg(addr_id),count(1)
FROM phrase
GROUP BY tokenphrase;