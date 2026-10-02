-- 仅在运行 02_synthetic.sql 的同一个专用实验库中运行。
-- 请先完成并保存 baseline 的全部原始计划，再运行本文件采集 extended 对照。
-- 本文件只增加本实验统计对象并刷新统计，不改变表中数据或索引。
-- dependencies: 等值条件中的函数依赖；mcv: 高频联合取值组合。
-- ndistinct: 为多列 GROUP BY 等分组数估计提供信息，本轮 SPJ 不据此归因。
-- PostgreSQL 同表扩展统计不能被宣称为通用的跨表相关性解决方案。
BEGIN;

DROP STATISTICS IF EXISTS synthetic.st_corr_independent_city_zip;
DROP STATISTICS IF EXISTS synthetic.st_corr_dependent_city_zip;
DROP STATISTICS IF EXISTS synthetic.st_corr_skewed_city_zip;
DROP STATISTICS IF EXISTS synthetic.st_cross_orders_customer_zip;

CREATE STATISTICS synthetic.st_corr_independent_city_zip (dependencies, mcv, ndistinct)
    ON city, zipcode FROM synthetic.corr_independent;
CREATE STATISTICS synthetic.st_corr_dependent_city_zip (dependencies, mcv, ndistinct)
    ON city, zipcode FROM synthetic.corr_dependent;
CREATE STATISTICS synthetic.st_corr_skewed_city_zip (dependencies, mcv, ndistinct)
    ON city, zipcode FROM synthetic.corr_skewed;
CREATE STATISTICS synthetic.st_cross_orders_customer_zip (dependencies, mcv, ndistinct)
    ON customer_id, zipcode FROM synthetic.cross_orders;

ALTER STATISTICS synthetic.st_corr_independent_city_zip SET STATISTICS 1000;
ALTER STATISTICS synthetic.st_corr_dependent_city_zip SET STATISTICS 1000;
ALTER STATISTICS synthetic.st_corr_skewed_city_zip SET STATISTICS 1000;
ALTER STATISTICS synthetic.st_cross_orders_customer_zip SET STATISTICS 1000;

ANALYZE synthetic.corr_independent;
ANALYZE synthetic.corr_dependent;
ANALYZE synthetic.corr_skewed;
ANALYZE synthetic.cross_customers;
ANALYZE synthetic.cross_orders;

COMMIT;
