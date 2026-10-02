-- 仅在本项目专用 PostgreSQL 实验库中运行。
-- 本脚本会 DROP / 重建 synthetic schema，其中所有已有对象和数据均会删除。
-- synthetic 是本实验独占命名空间；不得在业务库或含有其他用途 synthetic 对象的库中运行。
-- 本脚本不删除或修改 tpch schema。建议调用 psql 时使用 ON_ERROR_STOP=1。
-- 人工 city/zipcode 编码用于控制相关性，并非真实地址资料。
BEGIN;

DROP SCHEMA IF EXISTS synthetic CASCADE;
CREATE SCHEMA synthetic;

CREATE TABLE synthetic.corr_independent (
    id integer PRIMARY KEY,
    city text NOT NULL,
    zipcode text NOT NULL
);
CREATE TABLE synthetic.corr_dependent (
    id integer PRIMARY KEY,
    city text NOT NULL,
    zipcode text NOT NULL
);
CREATE TABLE synthetic.corr_skewed (
    id integer PRIMARY KEY,
    city text NOT NULL,
    zipcode text NOT NULL
);

-- 300,000 行，100 × 100 组合各 30 行；每一列的 100 个值各 3,000 行。
-- PostgreSQL integer / integer 是整数除法，等于此处正整数的 floor。
INSERT INTO synthetic.corr_independent (id, city, zipcode)
SELECT g,
       'C' || lpad(((g - 1) % 100)::text, 2, '0'),
       'Z' || lpad((((g - 1) / 100) % 100)::text, 2, '0')
FROM generate_series(1, 300000) AS series(g);

-- 相同边际频率，但只有同号的 100 个组合，每个实际存在的组合 3,000 行。
INSERT INTO synthetic.corr_dependent (id, city, zipcode)
SELECT g,
       'C' || lpad(((g - 1) % 100)::text, 2, '0'),
       'Z' || lpad(((g - 1) % 100)::text, 2, '0')
FROM generate_series(1, 300000) AS series(g);

-- 150,000 行为热门 C00/Z00；其余 150,000 行均匀轮转到 99 个同号组合。
-- 稀有值每组 1,515 或 1,516 行；C42/Z42 恰为 1,515 行。
INSERT INTO synthetic.corr_skewed (id, city, zipcode)
SELECT g,
       'C' || lpad(code::text, 2, '0'),
       'Z' || lpad(code::text, 2, '0')
FROM (
    SELECT g,
           CASE WHEN g <= 150000 THEN 0
                ELSE 1 + ((g - 150001) % 99) END AS code
    FROM generate_series(1, 300000) AS series(g)
) AS generated;

-- 跨表对照：客户有 city，订单有 zipcode，相关关系横跨两张表。
-- 10,000 个客户，每个客户有 30 笔订单；每个城市 100 个客户。
CREATE TABLE synthetic.cross_customers (
    id integer PRIMARY KEY,
    city text NOT NULL
);
CREATE TABLE synthetic.cross_orders (
    id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES synthetic.cross_customers(id),
    zipcode text NOT NULL
);

INSERT INTO synthetic.cross_customers (id, city)
SELECT g, 'C' || lpad(((g - 1) % 100)::text, 2, '0')
FROM generate_series(1, 10000) AS series(g);

INSERT INTO synthetic.cross_orders (id, customer_id, zipcode)
SELECT g,
       1 + ((g - 1) % 10000),
       'Z' || lpad(((g - 1) % 100)::text, 2, '0')
FROM generate_series(1, 300000) AS series(g);

-- target 1000 请求至多约 300,000 行 ANALYZE 样本，覆盖本实验表规模。
-- 三组同表实验使用相同结构及单列统计目标；不额外建立 city/zipcode 索引。
ALTER TABLE synthetic.corr_independent ALTER COLUMN city SET STATISTICS 1000;
ALTER TABLE synthetic.corr_independent ALTER COLUMN zipcode SET STATISTICS 1000;
ALTER TABLE synthetic.corr_dependent ALTER COLUMN city SET STATISTICS 1000;
ALTER TABLE synthetic.corr_dependent ALTER COLUMN zipcode SET STATISTICS 1000;
ALTER TABLE synthetic.corr_skewed ALTER COLUMN city SET STATISTICS 1000;
ALTER TABLE synthetic.corr_skewed ALTER COLUMN zipcode SET STATISTICS 1000;
ALTER TABLE synthetic.cross_customers ALTER COLUMN city SET STATISTICS 1000;
ALTER TABLE synthetic.cross_orders ALTER COLUMN customer_id SET STATISTICS 1000;
ALTER TABLE synthetic.cross_orders ALTER COLUMN zipcode SET STATISTICS 1000;

ANALYZE synthetic.corr_independent;
ANALYZE synthetic.corr_dependent;
ANALYZE synthetic.corr_skewed;
ANALYZE synthetic.cross_customers;
ANALYZE synthetic.cross_orders;

COMMENT ON SCHEMA synthetic IS 'B/C experiment: deterministic synthetic controls; safe to recreate only in this dedicated lab database';
COMMENT ON TABLE synthetic.corr_independent IS '300000 rows; independent city/zipcode; identical marginals to corr_dependent';
COMMENT ON TABLE synthetic.corr_dependent IS '300000 rows; perfect city/zipcode correlation; each matching pair has 3000 rows';
COMMENT ON TABLE synthetic.corr_skewed IS '300000 rows; 50 percent hot correlated pair and 99 rare correlated pairs';
COMMENT ON TABLE synthetic.cross_orders IS '300000 rows; zipcode correlated with customer city across tables';

COMMIT;
