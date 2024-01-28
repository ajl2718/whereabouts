INSERT INTO skipphraseinverted
SELECT tokenphrase, array_agg(addr_id), count(1)
FROM skipphrase
GROUP BY tokenphrase;