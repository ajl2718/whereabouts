--
INSERT INTO trigramphraseinverted
SELECT trigramphrase, array_agg(addr_id), count(1)
FROM trigramphrase
GROUP BY trigramphrase;