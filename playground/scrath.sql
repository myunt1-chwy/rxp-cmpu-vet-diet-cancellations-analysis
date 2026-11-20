WITH lines AS (
    SELECT
        TO_VARCHAR(ORDER_ID) a.order_id,
        TO_VARCHAR(ORDER_LINE_ID) a.line_id,
        TO_VARCHAR(CUSTOMER_ID) a.customer_id,
        TO_VARCHAR(PET_ID) a.pet_id,
        TO_VARCHAR(PARENT_PRODUCT_PART_NUMBER) a.product_id,
        TO_VARCHAR(RX_ID) a.rx_id,
        MIN(a.ORDER_PLACED_DTTM) placed_ts,
        MIN(a.ORDER_CANCEL_DTTM) cancel_ts,
        MIN(a.ORDER_LINE_SHIPPED_DTTM) shipped_ts,
        MAX(a.ORDER_CANCEL_REASON) cancel_reason
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP a
    JOIn ECOM.ORDERS o on
    on  a.order_id = o.order_id
    WHERE a.IS_VET_DIET_FLAG = TRUE
      AND a.ORDER_PLACED_DTTM_EST >= DATEADD(MONTH, -3, CURRENT_DATE())
    GROUP BY 1,2,3,4,5,6
),
aged AS (
    SELECT *
    FROM lines
    WHERE cancel_ts >= DATEADD(MONTH, -3, CURRENT_DATE())
      AND cancel_ts < DATEADD(DAY, -30, CURRENT_DATE())
      AND cancel_reason ILIKE '%AGED%'
      AND shipped_ts IS NULL
      AND customer_id IS NOT NULL
      AND pet_id IS NOT NULL
      AND product_id IS NOT NULL
      AND rx_id IS NOT NULL
      AND placed_ts IS NOT NULL
      AND DATEDIFF(MINUTE, placed_ts, cancel_ts) >= 14400
      AND DATEDIFF(MINUTE, placed_ts, cancel_ts) < 18720
),
rx AS (
    SELECT
        TO_VARCHAR(RX_ID) rx_id,
        TO_VARCHAR(CUSTOMER_ID) customer_id,
        TO_VARCHAR(PET_ID) pet_id,
        TO_VARCHAR(PARENT_PRODUCT_PART_NUMBER) product_id,
        RX_CREATION_DATETIME created_ts,
        MIN_APPROVED_DATETIME approved_ts,
        APPROVAL_CHANNEL channel
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE IS_VET_DIET_FLAG = TRUE
      AND MIN_APPROVED_DATETIME IS NOT NULL
      AND MIN_APPROVED_DATETIME >= DATEADD(MONTH, -3, CURRENT_DATE())
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY RX_ID
        ORDER BY MIN_APPROVED_DATETIME
    ) = 1
),
nonupload AS (
    SELECT
        c.line_id,
        p.rx_id approved_rx_id,
        p.approved_ts,
        p.channel,
        IFF(
            p.rx_id = c.rx_id,
            'ORIGINAL RX',
            'DIFFERENT RX'
        ) match_type
    FROM aged c
    JOIN rx p
      ON c.customer_id = p.customer_id
     AND c.pet_id = p.pet_id
     AND c.product_id = p.product_id
)
select channel, count(*) from  nonupload group by 1 order by 2;
-- | CHANNEL         | COUNT(*) |
-- |-----------------+----------|
-- | PARTNER         |       11 |
-- | RHAPSODY        |       14 |
-- | CLINIC_EMAIL    |       36 |
-- | SNAIL_MAIL      |       43 |
-- | RE_AUTH         |       56 |
-- | VERBAL          |      248 |
-- | FAX             |      312 |
-- | PH              |      577 |
-- | CUSTOMER_EMAIL  |      598 |
-- | CUSTOMER_UPLOAD |     3634 |






WITH lines AS (
    SELECT
        a.order_status,
        o.order_status_description,
        b.approval_channel,
        TO_VARCHAR(a.ORDER_ID) order_id,
        TO_VARCHAR(a.ORDER_LINE_ID) line_id,
        TO_VARCHAR(a.CUSTOMER_ID) customer_id,
        TO_VARCHAR(a.PET_ID) pet_id,
        TO_VARCHAR(a.PARENT_PRODUCT_PART_NUMBER) product_id,
        TO_VARCHAR(a.RX_ID) rx_id,
        MIN(a.ORDER_PLACED_DTTM) placed_ts,
        MIN(a.ORDER_CANCEL_DTTM) cancel_ts,
        MIN(a.ORDER_LINE_SHIPPED_DTTM) shipped_ts,
        MAX(a.ORDER_CANCEL_REASON) cancel_reason
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP a
    JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS b
    on a.rx_id = b.rx_id
    JOIN ECOM.ORDERS o
    on a.order_id = o.order_id
    WHERE a.IS_VET_DIET_FLAG = TRUE
      and b.IS_VET_DIET_FLAG = TRUE
      and b.approval_channel = 'CUSTOMER_UPLOAD'
      AND a.ORDER_PLACED_DTTM_EST >= DATEADD(MONTH, -3, CURRENT_DATE())
    GROUP BY 1,2,3,4,5,6,7,8,9
)
select rx_id from lines where shipped_ts is not null
and cancel_reason is null limit 5;

    -- select order_id
-- from lines
-- where shipped_ts is null
-- and DATEDIFF(MINUTE, placed_ts, cancel_ts) >= 14400
-- AND DATEDIFF(MINUTE, placed_ts, cancel_ts) < 18720
-- and cancel_reason ilike '%aged%'
-- limit 5;




-- Canceled order ids
-- ***************************[ 1 ]***************************
-- ORDER_ID      | 5201006513
-- RX_ID         | DT107102830
-- CANCEL_REASON | Aged Order
-- ***************************[ 2 ]***************************
-- ORDER_ID      | 5198450558
-- RX_ID         | DT107047960
-- CANCEL_REASON | Aged Order
-- ***************************[ 3 ]***************************
-- ORDER_ID      | 5198992760
-- RX_ID         | DT107059521
-- CANCEL_REASON | Aged Order
-- ***************************[ 4 ]***************************
-- ORDER_ID      | 5183992083
-- RX_ID         | DT106820518
-- CANCEL_REASON | Aged Order
-- ***************************[ 5 ]***************************
-- ORDER_ID      | 5190410421
-- RX_ID         | DT106953645
-- CANCEL_REASON | Aged Order


-- Shipped
    * The query returned 5 Rx IDs. Each one is a vet diet prescription approved
  by customer upload, placed in the last 3 months, with a shipped line and
  no cancel reason:

  ┌─────────────┐
  │ RX_ID       │
  ├─────────────┤
  │ DT106678730 │
  ├─────────────┤
  │ DT107754134 │
  ├─────────────┤
  │ DT106824788 │
  ├─────────────┤
  │ DT105469768 │
  ├─────────────┤
  │ DT105965391 │
  └─────────────┘
