# SQL 查询清单

共 20 条教学 SPJ 查询，12 条在 TPC-H 数据上派生，8 条在合成数据上执行；不是官方 TPC-H Q1 至 Q22，也不产生 TPC-H 性能评分。

## T01 单表：订单状态常见值

场景：`single`；数据：`tpch`。

```sql
SELECT o_orderkey FROM tpch.orders WHERE o_orderstatus = 'F';
```

## T02 单表：订单日期窄范围

场景：`single`；数据：`tpch`。

```sql
SELECT o_orderkey FROM tpch.orders WHERE o_orderdate >= DATE '1995-01-01' AND o_orderdate < DATE '1995-02-01';
```

## T03 单表：明细发货日期范围

场景：`single`；数据：`tpch`。

```sql
SELECT l_orderkey FROM tpch.lineitem WHERE l_shipdate >= DATE '1994-01-01' AND l_shipdate < DATE '1995-01-01';
```

## T04 单表：品牌与尺寸双条件

场景：`single`；数据：`tpch`。

```sql
SELECT p_partkey FROM tpch.part WHERE p_brand = 'Brand#23' AND p_size BETWEEN 1 AND 10;
```

## T05 单表：客户市场类别

场景：`single`；数据：`tpch`。

```sql
SELECT c_custkey FROM tpch.customer WHERE c_mktsegment = 'BUILDING';
```

## T06 两表：客户类别向订单传播

场景：`simple_join`；数据：`tpch`。

```sql
SELECT o.o_orderkey FROM tpch.customer c JOIN tpch.orders o ON o.o_custkey = c.c_custkey WHERE c.c_mktsegment = 'BUILDING';
```

## T07 两表：订单日期与明细折扣

场景：`simple_join`；数据：`tpch`。

```sql
SELECT l.l_orderkey FROM tpch.orders o JOIN tpch.lineitem l ON l.l_orderkey = o.o_orderkey WHERE o.o_orderdate >= DATE '1995-01-01' AND o.o_orderdate < DATE '1995-04-01' AND l.l_discount BETWEEN 0.05 AND 0.07;
```

## T08 两表：供应商与国家维表

场景：`simple_join`；数据：`tpch`。

```sql
SELECT s.s_suppkey FROM tpch.supplier s JOIN tpch.nation n ON n.n_nationkey = s.s_nationkey WHERE n.n_name = 'GERMANY';
```

## T09 三表：客户订单明细及日期条件

场景：`multi_join`；数据：`tpch`。

```sql
SELECT l.l_orderkey FROM tpch.customer c JOIN tpch.orders o ON o.o_custkey = c.c_custkey JOIN tpch.lineitem l ON l.l_orderkey = o.o_orderkey WHERE c.c_mktsegment = 'BUILDING' AND o.o_orderdate < DATE '1995-03-15' AND l.l_shipdate > DATE '1995-03-15';
```

## T10 四表：零件供应商与国家

场景：`multi_join`；数据：`tpch`。

```sql
SELECT ps.ps_partkey FROM tpch.part p JOIN tpch.partsupp ps ON ps.ps_partkey = p.p_partkey JOIN tpch.supplier s ON s.s_suppkey = ps.ps_suppkey JOIN tpch.nation n ON n.n_nationkey = s.s_nationkey WHERE p.p_size = 15 AND p.p_type LIKE '%BRASS' AND n.n_name = 'GERMANY';
```

## T11 五表：地域到订单明细的链式连接

场景：`multi_join`；数据：`tpch`。

```sql
SELECT l.l_orderkey FROM tpch.region r JOIN tpch.nation n ON n.n_regionkey = r.r_regionkey JOIN tpch.customer c ON c.c_nationkey = n.n_nationkey JOIN tpch.orders o ON o.o_custkey = c.c_custkey JOIN tpch.lineitem l ON l.l_orderkey = o.o_orderkey WHERE r.r_name = 'ASIA' AND o.o_orderdate >= DATE '1994-01-01' AND o.o_orderdate < DATE '1995-01-01';
```

## T12 六表：增加客户与供应商同国约束

场景：`multi_join`；数据：`tpch`。

```sql
SELECT l.l_orderkey FROM tpch.region r JOIN tpch.nation n ON n.n_regionkey = r.r_regionkey JOIN tpch.customer c ON c.c_nationkey = n.n_nationkey JOIN tpch.orders o ON o.o_custkey = c.c_custkey JOIN tpch.lineitem l ON l.l_orderkey = o.o_orderkey JOIN tpch.supplier s ON s.s_suppkey = l.l_suppkey AND s.s_nationkey = n.n_nationkey WHERE r.r_name = 'ASIA' AND o.o_orderdate >= DATE '1994-01-01' AND o.o_orderdate < DATE '1995-01-01';
```

## S13 独立数据：单列城市过滤

场景：`independent`；数据：`synthetic`。

```sql
SELECT id FROM synthetic.corr_independent WHERE city = 'C00';
```

## S14 相关数据：单列城市过滤

场景：`correlated`；数据：`synthetic`。

```sql
SELECT id FROM synthetic.corr_dependent WHERE city = 'C00';
```

## S15 独立数据：城市与邮编联合过滤

场景：`independent`；数据：`synthetic`。

```sql
SELECT id FROM synthetic.corr_independent WHERE city = 'C00' AND zipcode = 'Z00';
```

## S16 强相关：城市与邮编匹配组合

场景：`correlated`；数据：`synthetic`。

```sql
SELECT id FROM synthetic.corr_dependent WHERE city = 'C00' AND zipcode = 'Z00';
```

## S17 负对照：不存在的城市邮编组合

场景：`correlated`；数据：`synthetic`。

```sql
SELECT id FROM synthetic.corr_dependent WHERE city = 'C00' AND zipcode = 'Z01';
```

## S18 倾斜相关：热门城市与邮编

场景：`skew`；数据：`synthetic`。

```sql
SELECT id FROM synthetic.corr_skewed WHERE city = 'C00' AND zipcode = 'Z00';
```

## S19 倾斜相关：稀有城市与邮编

场景：`skew`；数据：`synthetic`。

```sql
SELECT id FROM synthetic.corr_skewed WHERE city = 'C42' AND zipcode = 'Z42';
```

## S20 跨表相关：客户城市与订单邮编

场景：`cross_table`；数据：`synthetic`。

```sql
SELECT o.id FROM synthetic.cross_customers c JOIN synthetic.cross_orders o ON o.customer_id = c.id WHERE c.city = 'C00' AND o.zipcode = 'Z00';
```
