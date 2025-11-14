# Assignment 2 — Analysis Report (auto-generated)


Generated: 2025-11-14T09:32:19.862763 UTC


**Note**: Figures and CSV outputs are in the `analysis_output/` folder.


## Discovered HAR files


- `crawl_data_accept/ad.nl.har`

- `crawl_data_accept/apnews.com.har`

- `crawl_data_accept/axios.com.har`

- `crawl_data_accept/bbc.co.uk.har`

- `crawl_data_accept/bloomberg.com.har`

- `crawl_data_accept/businessinsider.com.har`

- `crawl_data_accept/buzzfeed.com.har`

- `crawl_data_accept/cbsnews.com.har`

- `crawl_data_accept/cnbc.com.har`

- `crawl_data_accept/cnn.com.har`

- `crawl_data_accept/corriere.it.har`

- `crawl_data_accept/dailymail.co.uk.har`

- `crawl_data_accept/dw.com.har`

- `crawl_data_accept/foxnews.com.har`

- `crawl_data_accept/france24.com.har`

- `crawl_data_accept/gazzetta.it.har`

- `crawl_data_accept/huffpost.com.har`

- `crawl_data_accept/latimes.com.har`

- `crawl_data_accept/lefigaro.fr.har`

- `crawl_data_accept/lemonde.fr.har`

- `crawl_data_accept/libero.it.har`

- `crawl_data_accept/msn.com.har`

- `crawl_data_accept/msnbc.com.har`

- `crawl_data_accept/n-tv.de.har`

- `crawl_data_accept/nbcnews.com.har`

- `crawl_data_accept/newsweek.com.har`

- `crawl_data_accept/nltimes.nl.har`

- `crawl_data_accept/nos.nl.har`

- `crawl_data_accept/nu.nl.har`

- `crawl_data_accept/nypost.com.har`

- `crawl_data_accept/nytimes.com.har`

- `crawl_data_accept/repubblica.it.har`

- `crawl_data_accept/reuters.com.har`

- `crawl_data_accept/rtl.de.har`

- `crawl_data_accept/skynews.com.har`

- `crawl_data_accept/telegraaf.nl.har`

- `crawl_data_accept/the-sun.com.har`

- `crawl_data_accept/theguardian.com.har`

- `crawl_data_accept/washingtonpost.com.har`

- `crawl_data_accept/wsj.com.har`


## 1 — Box plots comparing crawls


![Number of requests per website](analysis_output/boxplot_total_requests.png)

![Number of third-party requests per website](analysis_output/boxplot_third_party_requests.png)

![Number of distinct third-party domains per website](analysis_output/boxplot_num_third_party_domains.png)

![Number of distinct entities per website](analysis_output/boxplot_num_third_party_entities.png)


## 2 — Numeric summary (Min/Median/Max)


CSV: `analysis_output/crawl_metric_summary_min_median_max.csv`



## 3 — Advertising / Analytics presence per crawl


CSV: `analysis_output/ad_analytics_site_counts.csv`


Plots: `analysis_output/bar_advertising_sites.png`, `analysis_output/bar_analytics_sites.png`



## 4 — US vs EU (Accept) summary


CSV: `analysis_output/us_vs_eu_accept_metrics.csv`



## 5 — US vs EU Advertising/Analytics (Accept)


Plots: `analysis_output/us_eu_advertising_accept.png`, `analysis_output/us_eu_analytics_accept.png`



## 6 — Cookies observed


CSV: `analysis_output/observed_cookies.csv`



## 7 — Top 10 third-party domains per crawl


- `analysis_output/top10_third_parties_Accept.csv`

- `analysis_output/top10_third_parties_Reject.csv`

- `analysis_output/top10_third_parties_Block.csv`


## 8 — Top sites by number of distinct third-party domains


- `analysis_output/top10_sites_by_thirdparties_Accept.csv`

- `analysis_output/top10_sites_by_thirdparties_Reject.csv`

- `analysis_output/top10_sites_by_thirdparties_Block.csv`


## 9 — Top visits by distinct server IP addresses


- `analysis_output/top10_by_server_ip_counts.csv`


## 10 — Permissions-Policy disabled counts


- `analysis_output/permissions_policy_disabled_counts.csv`


## 11 — Referrer-Policy non-default occurrences


- `analysis_output/referrer_policy_non_default_counts.csv`


## 12 — Accept-CH tokens observed


- `analysis_output/accept_ch_top_tokens.csv`


## 13 — Cross-entity redirections


- `analysis_output/cross_entity_redirections.csv`


## 14 — CNAME checks


- `analysis_output/cname_checks.txt`


## 15 — Reflections


- `analysis_output/reflections.txt`