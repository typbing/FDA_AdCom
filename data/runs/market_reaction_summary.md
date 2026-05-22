# Market Reaction Label Summary

## Coverage

- Total rows: 57
- Rows with ticker: 17
- Rows with briefing_pdf_release_date: 55
- Rows with computed market_label: 9
- Rows with market price errors: 8

## Computed Labels

| document_id | ticker_used | release_date | market_label | abn_return_3d | return_3d | source |
|---|---|---:|---|---:|---:|---|
| 0b99a891dd01a3b2 | RHHBY | 2023-03-06 | NEUTRAL | 0.9946 | -3.1431 | PDF metadata /CreationDate |
| 6df8a6a4aa29769e | REGN | 2023-01-04 | DOWN | -5.2461 | -6.3318 | PDF metadata /CreationDate |
| 2252b7c3b1118d54 | PRGO | 2023-05-04 | DOWN | -5.8068 | -5.5766 | PDF metadata /CreationDate |
| 1b07cb209a078f7d | SNY | 2023-05-23 | NEUTRAL | -0.3904 | -3.4565 | PDF metadata /CreationDate |
| af190de57f8c9774 | PFE | 2023-03-13 | NEUTRAL | 0.1867 | 1.2795 | PDF metadata /CreationDate |
| dd6f0d626e63c30c | INVA | 2023-04-11 | NEUTRAL | 0.4623 | 1.7782 | PDF metadata /CreationDate |
| 3ea9b6d3e184b0d5 | REGN | 2023-01-04 | DOWN | -5.2461 | -6.3318 | PDF metadata /CreationDate |
| 08d7a4cf68c80338 | RHHBY | 2023-03-06 | NEUTRAL | 0.9946 | -3.1431 | PDF metadata /CreationDate |
| 74f2619b703a09c2 | REGN | 2023-01-05 | DOWN | -4.4975 | -3.4279 | PDF metadata /CreationDate |

## Price Source Errors

- 2b2013a2acf6a3ce | CDTX | 2023-01-19 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/CDTX?period1=1673247600&period2=1676703600&interval=1d&events=history
- f8bbf578a35e0569 | HZNP | 2019-12-10 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/HZNP?period1=1575097200&period2=1578553200&interval=1d&events=history
- 07d0a87f7ff02db9 | CDTX | 2023-01-19 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/CDTX?period1=1673247600&period2=1676703600&interval=1d&events=history
- 07ae88dc3a7a1552 | HZNP | 2019-12-10 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/HZNP?period1=1575097200&period2=1578553200&interval=1d&events=history
- 765741af520c206b | HZNP | 2019-12-12 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/HZNP?period1=1575270000&period2=1578726000&interval=1d&events=history
- fd90bab1d0efa617 | CDTX | 2023-01-23 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/CDTX?period1=1673593200&period2=1677049200&interval=1d&events=history
- dd15c80512cccec8 | HZNP | 2019-12-04 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/HZNP?period1=1574578800&period2=1578034800&interval=1d&events=history
- 66e326fd862af572 | CDTX | 2023-01-18 | MARKET_ERROR: 404 Client Error: Not Found for url: https://query1.finance.yahoo.com/v8/finance/chart/CDTX?period1=1673161200&period2=1676617200&interval=1d&events=history

## Notes

- Release dates are currently inferred from PDF metadata or media Last-Modified headers, not manually verified FDA posting timestamps.
- Market labels use 3-day abnormal return versus IBB.
- Delisted/acquired tickers such as HZNP and unavailable Yahoo tickers such as CDTX need a fallback price source before they can be labeled.
