    WITH lines AS (
    SELECT
        TO_VARCHAR(ORDER_ID) order_id,
        TO_VARCHAR(ORDER_LINE_ID) line_id,
        TO_VARCHAR(CUSTOMER_ID) customer_id,
        TO_VARCHAR(PET_ID) pet_id,
        TO_VARCHAR(PARENT_PRODUCT_PART_NUMBER) product_id,
        TO_VARCHAR(RX_ID) rx_id,
        MIN(ORDER_PLACED_DTTM) placed_ts,
        MIN(ORDER_CANCEL_DTTM) cancel_ts,
        MIN(ORDER_LINE_SHIPPED_DTTM) shipped_ts,
        MAX(ORDER_CANCEL_REASON) cancel_reason
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP
    WHERE IS_VET_DIET_FLAG = TRUE
      AND ORDER_PLACED_DTTM_EST >= DATEADD(MONTH, -13, CURRENT_DATE())
    GROUP BY 1,2,3,4,5,6
),

aged AS (
    SELECT *
    FROM lines
    WHERE cancel_ts >= DATEADD(MONTH, -12, CURRENT_DATE())
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
      AND MIN_APPROVED_DATETIME >= DATEADD(MONTH, -13, CURRENT_DATE())
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY RX_ID
        ORDER BY MIN_APPROVED_DATETIME
    ) = 1
),

reorders AS (
    SELECT
        c.line_id original_line_id,
        n.order_id new_order_id,
        n.rx_id new_rx_id,
        n.placed_ts reorder_ts,
        n.shipped_ts reorder_shipped_ts
    FROM aged c
    JOIN lines n
      ON c.customer_id = n.customer_id
     AND c.pet_id = n.pet_id
     AND c.product_id = n.product_id
     AND c.order_id <> n.order_id
     AND n.placed_ts > c.cancel_ts
     AND n.placed_ts <= DATEADD(DAY, 30, c.cancel_ts)
),

first_reorder AS (
    SELECT *
    FROM reorders
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY original_line_id
        ORDER BY reorder_ts, new_order_id
    ) = 1
),

shipped_reorder AS (
    SELECT
        original_line_id,
        MIN(reorder_shipped_ts) shipped_ts
    FROM reorders
    WHERE reorder_shipped_ts IS NOT NULL
      AND reorder_shipped_ts >= reorder_ts
    GROUP BY 1
),

nonupload AS (
    SELECT
        c.line_id original_line_id,
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
    LEFT JOIN first_reorder f
      ON c.line_id = f.original_line_id
    WHERE p.approved_ts > c.cancel_ts
      AND p.approved_ts <= DATEADD(DAY, 30, c.cancel_ts)
      AND p.channel IN (
          'PH','FAX','CUSTOMER_EMAIL','VERBAL',
          'CLINIC_EMAIL','RHAPSODY','SNAIL_MAIL',
          'PARTNER','RE_AUTH'
      )
      AND (
          p.rx_id = c.rx_id
          OR p.created_ts >= c.placed_ts
      )
      AND (
          f.reorder_ts IS NULL
          OR p.approved_ts < f.reorder_ts
      )
),

first_nonupload AS (
    SELECT *
    FROM nonupload
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY original_line_id
        ORDER BY
            approved_ts,
            IFF(match_type = 'ORIGINAL RX', 0, 1)
    ) = 1
),

original_rx AS (
    SELECT
        original_line_id,
        MIN(approved_ts) approved_ts
    FROM nonupload
    WHERE match_type = 'ORIGINAL RX'
    GROUP BY 1
),

first_upload AS (
    SELECT
        n.original_line_id,
        n.new_order_id,
        n.reorder_ts,
        p.approved_ts
    FROM reorders n
    JOIN rx p ON n.new_rx_id = p.rx_id
    JOIN aged c ON n.original_line_id = c.line_id
    WHERE p.channel = 'CUSTOMER_UPLOAD'
      AND p.approved_ts >= n.reorder_ts
      AND p.approved_ts <= DATEADD(DAY, 30, c.cancel_ts)
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY n.original_line_id
        ORDER BY n.reorder_ts, p.approved_ts
    ) = 1
),

base AS (
    SELECT
        c.order_id,
        c.customer_id,
        c.placed_ts,
        c.cancel_ts,
        n.approved_ts nonupload_ts,
        n.channel nonupload_channel,
        n.match_type,
        o.approved_ts original_rx_ts,
        f.new_order_id first_reorder_id,
        f.reorder_ts first_reorder_ts,
        u.new_order_id upload_reorder_id,
        u.reorder_ts upload_reorder_ts,
        s.shipped_ts first_reorder_shipped_ts,

        ROUND(
            DATEDIFF(MINUTE,c.cancel_ts,n.approved_ts)/1440.0,2
        ) days_to_nonupload,

        ROUND(
            DATEDIFF(MINUTE,c.cancel_ts,f.reorder_ts)/1440.0,2
        ) days_to_reorder,

        ROUND(
            DATEDIFF(MINUTE,c.cancel_ts,u.reorder_ts)/1440.0,2
        ) days_to_upload_reorder

    FROM aged c
    LEFT JOIN first_nonupload n
      ON c.line_id = n.original_line_id
    LEFT JOIN original_rx o
      ON c.line_id = o.original_line_id
    LEFT JOIN first_reorder f
      ON c.line_id = f.original_line_id
    LEFT JOIN first_upload u
      ON c.line_id = u.original_line_id
    LEFT JOIN shipped_reorder s
      ON c.line_id = s.original_line_id
),

segments AS (
    SELECT
        s.value:sec::VARCHAR report_section,
        s.value:seg::VARCHAR segment,
        b.*

    FROM base b,
    LATERAL FLATTEN(
        INPUT => ARRAY_CONSTRUCT_COMPACT(

          OBJECT_CONSTRUCT(
              'sec','01. BASELINE',
              'seg','All aged canceled lines'
          ),

          IFF(nonupload_ts IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','02. NON-UPLOAD APPROVALS',
                  'seg','Any non-upload approval before reorder'
              ), NULL),

          IFF(original_rx_ts IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','02. NON-UPLOAD APPROVALS',
                  'seg','Original Rx approved after cancellation'
              ), NULL),

          IFF(nonupload_ts IS NOT NULL
              AND match_type = 'DIFFERENT RX',
              OBJECT_CONSTRUCT(
                  'sec','02. NON-UPLOAD APPROVALS',
                  'seg','First non-upload approval on different Rx'
              ), NULL),

          IFF(nonupload_ts <= DATEADD(DAY,14,placed_ts),
              OBJECT_CONSTRUCT(
                  'sec','03. EXTENSION SCENARIOS',
                  'seg','Non-upload approved by Day 14'
              ), NULL),

          IFF(nonupload_ts <= DATEADD(DAY,17,placed_ts),
              OBJECT_CONSTRUCT(
                  'sec','03. EXTENSION SCENARIOS',
                  'seg','Non-upload approved by Day 17'
              ), NULL),

          IFF(nonupload_ts <= DATEADD(DAY,21,placed_ts),
              OBJECT_CONSTRUCT(
                  'sec','03. EXTENSION SCENARIOS',
                  'seg','Non-upload approved by Day 21'
              ), NULL),

          IFF(original_rx_ts <= DATEADD(DAY,14,placed_ts),
              OBJECT_CONSTRUCT(
                  'sec','04. ORIGINAL RX EXTENSION',
                  'seg','Original Rx approved by Day 14'
              ), NULL),

          IFF(original_rx_ts <= DATEADD(DAY,17,placed_ts),
              OBJECT_CONSTRUCT(
                  'sec','04. ORIGINAL RX EXTENSION',
                  'seg','Original Rx approved by Day 17'
              ), NULL),

          IFF(original_rx_ts <= DATEADD(DAY,21,placed_ts),
              OBJECT_CONSTRUCT(
                  'sec','04. ORIGINAL RX EXTENSION',
                  'seg','Original Rx approved by Day 21'
              ), NULL),

          IFF(nonupload_ts IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','05. APPROVAL CHANNEL',
                  'seg',COALESCE(nonupload_channel,'UNKNOWN')
              ), NULL),

          IFF(nonupload_ts IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','06. APPROVAL DELAY',
                  'seg',
                  CASE
                      WHEN days_to_nonupload <= 1
                          THEN '01. Within 24 hours'
                      WHEN days_to_nonupload <= 3
                          THEN '02. 1-3 days'
                      WHEN days_to_nonupload <= 7
                          THEN '03. 3-7 days'
                      WHEN days_to_nonupload <= 14
                          THEN '04. 7-14 days'
                      ELSE '05. 14-30 days'
                  END
              ), NULL),

          IFF(first_reorder_id IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','07. REORDER OUTCOMES',
                  'seg','Any subsequent order within 30 days'
              ), NULL),

          IFF(upload_reorder_id IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','07. REORDER OUTCOMES',
                  'seg','Subsequent order approved via Customer Upload'
              ), NULL),

          IFF(first_reorder_shipped_ts IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','07. REORDER OUTCOMES',
                  'seg','Subsequent order shipped'
              ), NULL),

          IFF(first_reorder_ts IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','08. REORDER TIMING',
                  'seg',
                  CASE
                      WHEN days_to_reorder <= 1
                          THEN '01. Within 24 hours'
                      WHEN days_to_reorder <= 3
                          THEN '02. 1-3 days'
                      WHEN days_to_reorder <= 7
                          THEN '03. 3-7 days'
                      WHEN days_to_reorder <= 14
                          THEN '04. 7-14 days'
                      ELSE '05. 14-30 days'
                  END
              ), NULL),

          IFF(upload_reorder_id IS NOT NULL,
              OBJECT_CONSTRUCT(
                  'sec','09. UPLOAD REORDER TIMING',
                  'seg',
                  CASE
                      WHEN days_to_upload_reorder <= 1
                          THEN '01. Within 24 hours'
                      WHEN days_to_upload_reorder <= 3
                          THEN '02. 1-3 days'
                      WHEN days_to_upload_reorder <= 7
                          THEN '03. 3-7 days'
                      WHEN days_to_upload_reorder <= 14
                          THEN '04. 7-14 days'
                      ELSE '05. 14-30 days'
                  END
              ), NULL),

          OBJECT_CONSTRUCT(
              'sec','10. MONTHLY TREND',
              'seg',TO_CHAR(cancel_ts,'YYYY-MM')
          )

        )
    ) s
)

SELECT
    report_section,
    segment,

    COUNT(*) canceled_lines,
    COUNT(DISTINCT order_id) original_orders,
    COUNT(DISTINCT customer_id) customers,

    ROUND(
        100.0 * COUNT(*)
        / NULLIF((SELECT COUNT(*) FROM base),0),2
    ) pct_of_aged_canceled_lines,

    COUNT_IF(nonupload_ts IS NOT NULL)
        lines_with_nonupload_approval,

    COUNT_IF(original_rx_ts IS NOT NULL)
        lines_with_original_rx_approval,

    COUNT_IF(first_reorder_id IS NOT NULL)
        lines_with_subsequent_order,

    COUNT_IF(upload_reorder_id IS NOT NULL)
        lines_with_upload_approved_reorder,

    COUNT_IF(first_reorder_shipped_ts IS NOT NULL)
        lines_with_shipped_reorder,

    ROUND(AVG(days_to_nonupload),2)
        avg_days_cancel_to_nonupload_approval,

    ROUND(AVG(days_to_reorder),2)
        avg_days_cancel_to_first_reorder,

    ROUND(AVG(days_to_upload_reorder),2)
        avg_days_cancel_to_upload_reorder

FROM segments
GROUP BY 1,2
ORDER BY 1,2;
