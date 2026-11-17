# Official fund-data sources for Brazil, Russia and South Africa (research as of 2026-11-17/18)

Method and legend. VERIFIED = fetched this session from this host (real headers or sample rows seen) or read from the repo's own raw files. UNVERIFIED = from search snippets or background knowledge. UNOFFICIAL = not regulator/exchange/association/official platform. All requests were plain `curl`/WebFetch calls with a normal browser User-Agent; no access control was bypassed. Probe scripts were run from /tmp only; no repository code was edited. Prior notes (americas.md, europe_rest.md, asia_oceania_mea.md, 00_current_db_coverage.md) were re-checked and several of their claims are corrected below.

Access summary (this host, 2026-11-17):

| Host | Result |
|---|---|
| dados.cvm.gov.br (dataset pages and /dados/FI/... directory listings) | HTTP 403 Cloudflare challenge page, with both an app-style and a Chrome-style User-Agent, via curl and via WebFetch. Not bypassed. The project's own connector downloaded CVM files successfully on 2026-10-18, so access depends on host/IP and is intermittent. |
| www.jse.co.za (home and ETP page) | HTTP 403 (same body size 5,187 bytes on both URLs, a WAF page). Not bypassed. |
| iss.moex.com | 200, JSON, no key |
| www.cbr.ru | 200 |
| www.asisa.org.za, www.fsca.co.za, naufor.ru | 200 |
| api.bcb.gov.br | 200 |
| data.anbima.com.br | 200 (web UI); api.anbima.com.br returns 401 without client_id |
| sistemaswebb3-listados.b3.com.br | 200 but undocumented payload (returned empty results for my guesses) |
| dadosabertos.rfb.gov.br, brasilapi.com.br | 200 |

---

## 1. Brazil: why holdings are 0, what is loaded, and the CVM file/column facts

### Takeaway
Holdings are 0 because the CDA importer (`sync-cvm-holdings`) has simply never been run: `data/raw/brazil/` is empty and the repo's own technical report says "Implemented, no holdings rows in this snapshot". The importer also has probable correctness gaps (it ignores the new FIDC/FIAGRO/FIIM block files and does not read the CDA PL file by name). NAV exists for only 25,678 of 37,875 because the connector loads one month of Informe Diário (Oct 2026: 25,765 class/subclass keys), while the registry holds 36,869 classes and 10,720 subclasses. Registry fields (inception, manager, administrator, category) are already well covered.

### Cited Findings
- Never run: `data/raw/brazil/` is empty (the importer's download target is `data/raw/brazil/cda_fi_YYYYMM.zip`), and the report states no BR holdings rows are loaded. — repo `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/holdings/cvm_cda.py`, `reports/FundFlow_Complete_Technical_Report.md` (lines 33 and 50)
- `reports/brazil_france_holdings_research.md` (2026-10-27) calls the importer "Supported" but contains no run result and no real CDA header sample; its "field names vary" statement is untested. — repo `reports/brazil_france_holdings_research.md`
- What `sync-cvm-holdings --month YYYYMM` does (read from code): downloads `https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_YYYYMM.zip` (urllib, User-Agent `GlobalMutualFundETL/0.1` by default), reads every non-"confid" CSV, accepts files that have `CNPJ_FUNDO_CLASSE|CNPJ_FUNDO|CNPJ_FDO` and `DT_COMPTC|DT_COMPT`, maps market value from `VL_MERC_POS_FINAL`, quantity `QT_POS_FINAL`, name `DS_ATIVO`, ticker `CD_TICKER|CD_NEGOCIACAO`, ISIN `CD_ISIN`, net assets `VL_PATRIM_LIQ`; matches to DB `funds.source_fund_id` (CNPJ digits, optionally `:ID_SUBCLASSE`); first sets ALL BR funds to `holdings_status='unavailable'`, then writes `portfolio_holdings` and derives weights into `holding_metrics`. — repo `app/holdings/cvm_cda.py`
- Likely defects in the importer (code inspection, not run): (a) first statement bulk-resets all BR funds to unavailable before any load, so a failed/partial month wipes status; (b) only the one requested month is loaded and each run overwrites; (c) the CDA zip bundles per-block files (BLC_1..BLC_8), a PL file, and per-type files; the importer treats every CSV the same, so rows without `VL_MERC_POS_FINAL` produce rows with null value; (d) `CD_TICKER` is a guess, I could not verify that column exists; (e) default User-Agent may be challenged by Cloudflare the same way my probes were. All UNVERIFIED because the CDA zip could not be fetched.
- Registry structure (real sample, repo snapshot downloaded 2026-10-18, files dated 2026-10-17): `registro_fundo_classe.zip` contains `registro_fundo.csv` (90,646 rows), `registro_classe.csv` (36,869 rows), `registro_subclasse.csv` (10,720 rows), semicolon-delimited, latin-1. — repo `data/raw/cvm/registro_fundo_classe.zip`
- `registro_fundo.csv` header (VERIFIED): `ID_Registro_Fundo;CNPJ_Fundo;Codigo_CVM;Data_Registro;Data_Constituicao;Tipo_Fundo;Denominacao_Social;Data_Cancelamento;Situacao;Data_Inicio_Situacao;Data_Adaptacao_RCVM175;Data_Inicio_Exercicio_Social;Data_Fim_Exercicio_Social;Patrimonio_Liquido;Data_Patrimonio_Liquido;Diretor;CNPJ_Administrador;Administrador;Tipo_Pessoa_Gestor;CPF_CNPJ_Gestor;Gestor`. Fill rates measured: Gestor 70.8%, Administrador 71.4% (over all 90,646 rows incl. cancelled).
- `registro_classe.csv` header (VERIFIED): `ID_Registro_Fundo;ID_Registro_Classe;CNPJ_Classe;Codigo_CVM;Data_Registro;Data_Constituicao;Data_Inicio;Tipo_Classe;Denominacao_Social;Situacao;Data_Inicio_Situacao;Classificacao;Indicador_Desempenho;Classe_Cotas;Classificacao_Anbima;Tributacao_Longo_Prazo;Entidade_Investimento;Permitido_Aplicacao_CemPorCento_Exterior;Classe_ESG;Forma_Condominio;Exclusivo;Publico_Alvo;Patrimonio_Liquido;Data_Patrimonio_Liquido;CNPJ_Auditor;Auditor;CNPJ_Custodiante;Custodiante;CNPJ_Controlador;Controlador`. Measured fill: CNPJ 100%, Data_Inicio 100%, Classificacao 72.5%, Classificacao_Anbima 72.3%, Indicador_Desempenho (benchmark) 69.7%, Patrimonio_Liquido 92.2%, Custodiante 98.9%, Publico_Alvo 71.0%. No ISIN, ticker, gestor or administrador column in the class file (those are in registro_fundo, joined by `ID_Registro_Fundo`, which the connector does).
- `registro_subclasse.csv` header (VERIFIED): `ID_Registro_Classe;ID_Subclasse;Codigo_CVM;Data_Constituicao;Data_Inicio;Denominacao_Social;Situacao;Data_Inicio_Situacao;Forma_Condominio;Exclusivo;Publico_Alvo;Previdenciario;Exclusivo_INR;Exclusivo_Previdencia_Complementar`. `ID_Subclasse` is an alphanumeric code like `MZMRC1747322915`. Only the subclass name and status exist; no CNPJ (subclasses share the class CNPJ).
- Class composition (VERIFIED, 36,869 classes): situation Em Funcionamento Normal 33,807, Fase Pré-Operacional 2,267, Em Liquidação 758, Cancelado 37. By `Tipo_Classe`: FIF 26,744; FIDC 5,400; FIP 2,522; FII 1,539; FIAGRO 379; FIIM (index/ETF) 262; FIF (FAPI) 13; Funcine 8. Subclass situations: normal 6,268; pre-operational 4,033; in liquidation 230.
- Informe Diário (VERIFIED, `inf_diario_fi_202610.zip`, 252,726 rows, 25,765 distinct (CNPJ_FUNDO_CLASSE, ID_SUBCLASSE) keys of which 1,022 have a subclass): header `TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;VL_TOTAL;VL_QUOTA;VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST`; sample row `CLASSES - FIF;00.017.024/0001-53;;2026-10-01;1119426.37;44.990762600000;1221524.87;0.00;2902.97;1`. CNPJ carries punctuation (the connector strips non-digits). The single CSV is named `inf_diario_fi_YYYYMM.csv`. Includes class-level NAV (VL_QUOTA), net assets (VL_PATRIM_LIQ), daily subscriptions (CAPTC_DIA), redemptions (RESG_DIA), shareholders (NR_COTST). Rows with VL_QUOTA = 0 (placeholder) are rejected by the connector (697 rejects in reports/cvm_rejected_records.jsonl, mostly CNPJs absent from the class registry).
- Legacy `cad_fi.csv` (VERIFIED header, 17.9 MB, still published, but legacy/pre-RCVM 175): `TP_FUNDO;CNPJ_FUNDO;DENOM_SOCIAL;DT_REG;DT_CONST;CD_CVM;DT_CANCEL;SIT;DT_INI_SIT;DT_INI_ATIV;DT_INI_EXERC;DT_FIM_EXERC;CLASSE;DT_INI_CLASSE;RENTAB_FUNDO;CONDOM;FUNDO_COTAS;FUNDO_EXCLUSIVO;TRIB_LPRAZO;PUBLICO_ALVO;ENTID_INVEST;TAXA_PERFM;INF_TAXA_PERFM;TAXA_ADM;INF_TAXA_ADM;VL_PATRIM_LIQ;DT_PATRIM_LIQ;DIRETOR;CNPJ_ADMIN;ADMIN;PF_PJ_GESTOR;CPF_CNPJ_GESTOR;GESTOR;CNPJ_AUDITOR;AUDITOR;CNPJ_CUSTODIANTE;CUSTODIANTE;CNPJ_CONTROLADOR;CONTROLADOR;INVEST_CEMPR_EXTER;CLASSE_ANBIMA`. This is the only registry-level source of admin/performance fee (`TAXA_ADM`, `TAXA_PERFM`) I could see; the sample's early rows are cancelled funds with empty fee fields, fill for active funds not measured. Still downloaded by the connector but unused (only used as a manifest entry).
- Rename claims, checked: the CVM news page (via search snippet) says columns `TP_FUNDO`/`CNPJ_FUNDO` became `TP_FUNDO_CLASSE`/`CNPJ_FUNDO_CLASSE` with a notice dated 14/11/2024 (and `cda_fi_BLC_2` renamed `CNPJ_FUNDO_COTA` to `CNPJ_FUNDO_CLASSE_COTA`, added `ID_SUBCLASSE`, renamed `NM_FUNDO_COTA` to `NM_FUNDO_CLASSE_SUBCLASSE_COTA`). The previous researcher's date of 26/01/2026 is therefore not confirmed; the real sample (Oct 2026 file) already uses `CNPJ_FUNDO_CLASSE`, and the connector requires that name. — [CVM novidades page, via search result](https://dados.cvm.gov.br/pages/novidades) (page itself returned 403 to me; snippet only)
- CDA file rename, checked: the CDA dataset page (search snippet) states that from 8/11/2025 FIDC and FIAGRO positions were included in `cda_fiim_AAAAMM.csv` and `cda_fiim_CONFID_AAAAMM.csv`, and that "from 15/11/2025 the files will be renamed to `cda_fie_AAAAMM.csv` and `cda_fie_CONFID_AAAAMM.csv`" (fie = Fundos de Investimento Especiais, UNVERIFIED expansion). The search engine could not confirm the rename actually took place; no completion note was found. These are CSV names inside the monthly ZIP; the ZIP URL pattern `cda_fi_AAAAMM.zip` from the prior notes is believed unchanged (UNVERIFIED). — [CVM CDA dataset](https://dados.cvm.gov.br/dataset/fi-doc-cda) (snippet)
- Remaining CDA structure from CVM snippets/prior notes (UNVERIFIED, could not open): per-block files `cda_fi_BLC_1..8_AAAAMM.csv`, `cda_fi_PL_AAAAMM.csv`, `cda_fi_CONFID_AAAAMM.csv`; BLC_2 is investment in fund quotas. Exact BLC header lists could not be seen. Do not trust `CD_ISIN`/`CD_TICKER`/`CD_NEGOCIACAO` names until a real header is checked.
- Lâmina (UNVERIFIED headers): dataset `fi-doc-lamina`, monthly ZIPs `lamina_fi_AAAAMM.zip`, with a metadata dictionary at `https://dados.cvm.gov.br/dados/FI/DOC/LAMINA/META/meta_lamina_fi_txt.zip`; one third-party source says the package holds four sub-tables (lamina, carteira, rentab_ano, rentab_mes). The prior notes say the monthly listing starts Aug 2025. CVM historical folder exists at `/dados/FI/DOC/LAMINA/DADOS/HIST/`. — [CVM lâmina dataset](https://dados.cvm.gov.br/dataset/fi-doc-lamina) (snippet); [Alphacast mirror, UNOFFICIAL](https://preview.alphacast.io/datasets/fund-essential-information-lamina-cvm-49663)
- Perfil mensal (`FI/DOC/PERFIL_MENSAL/DADOS/perfil_mensal_fi_AAAAMM.csv`), balancete (`FI/DOC/BALANCETE/DADOS/balancete_fi_AAAAMM.zip`), extrato (`FI/DOC/EXTRATO/`): paths from prior notes/background, UNVERIFIED (all /dados/FI/DOC/ listings returned 403 to me). Recent CVM activity pages exist for `fie-doc-balanco` and `fii-doc-dfin` datasets (FIDC/FIAGRO and FII financial statements). — [CVM activity page](https://dados.cvm.gov.br/dataset/activity/fie-doc-balanco) (snippet)
- BCB SGS API (VERIFIED, 200 JSON, no key): `https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/2?formato=json` returned `[{"data":"13/11/2026","valor":"0.050788"},...]` (CDI daily). Useful for benchmarks (CDI = SGS 12, Selic 11, IPCA 433), not for fund data.
- ANBIMA: `https://data.anbima.com.br/` serves a public web UI (200; robots.txt disallows only /debentures-service/, /documentos-service/, /busca-service/, /debentures-consumer/, /workflow-service/). The programmatic API `https://api.anbima.com.br/feed/fundos/v2/fundos` returned HTTP 401 "Client Id ... invalid" without credentials (VERIFIED), so Feed de Fundos needs registered client_id/access token. ANBIMA developer docs list ICVM 555 funds and Offshore funds feeds. — [ANBIMA developers](https://developers.anbima.com.br/en/?p=143)
- B3: ETF, FII, FIAGRO, FIDC listing pages exist (descriptions only). The front-end listing proxy `https://sistemaswebb3-listados.b3.com.br/fundsProxy/fundsCall/GetListedFundsSIG/<base64 json>` answers 200 but my guessed payloads (typeFund 1..10) returned zero rows, so the payload is not known; no public documentation found. — [B3 ETF page](https://b3.com.br/pt_br/produtos-e-servicos/solucoes-para-emissores/fundos-de-investimentos/etfs-fundos-de-indices/), [B3 FII page](https://b3.com.br/pt_br/produtos-e-servicos/solucoes-para-emissores/fundos-de-investimentos/fundos-de-investimento-imobiliario/)
- brapi.dev offers a REST funds list (`/api/v2/funds/list?symbols=...&assetType=fiagro`, CNPJ and ticker) — UNOFFICIAL aggregator, token-based. — [brapi docs](https://brapi.dev/docs/fundos/listagem)
- Receita Federal CNPJ open data host `dadosabertos.rfb.gov.br` answers 200 (VERIFIED reachability). The full CNPJ base (Estabelecimentos, Empresas, Sócios) is a monthly bulk ZIP set; file names/columns UNVERIFIED this session. BrasilAPI `https://brasilapi.com.br/api/cnpj/v1/{cnpj}` returned 200 JSON (VERIFIED reachability) but is UNOFFICIAL (community mirror of RFB data).

### Why NAV is only 25,678 (cause, measured)
- The connector (`app/connectors/cvm.py`) builds `grouped` from ALL classes, then only appends NAV rows for the requested date window (default = current month, falling back to latest published month; max 12 monthly archives per run). `extract_nav_history` returns an empty tuple, so history only exists for months loaded in a run.
- Oct 2026 file: 25,765 distinct (class, subclass) keys with daily NAV versus 36,869 classes. The 11,000+ without NAV are structurally expected: FIDC (5,400), FIP (2,522), FII (1,539), FIAGRO (379) do not file the daily quota report in INF_DIARIO the way FIF do (they report monthly/quarterly or via B3), plus 2,267 pre-operational and 758 in liquidation. So the gap is mostly not a bug but different datasets and a one-month window.

### Field-by-field matrix (Brazil)
| Field | Best official source | Expected fill (of 33.8k active classes unless stated) |
|---|---|---|
| Daily NAV + history | CVM INF_DIARIO monthly zips (history back to 2000 per prior notes; UNVERIFIED depth) | FIF ~100% of active open funds; FII/FIAGRO via B3/CVM monthly info (see below); FIDC/FIP not daily |
| Net assets | INF_DIARIO VL_PATRIM_LIQ (daily); registro_classe Patrimonio_Liquido (92%) | ~95% FIF |
| Shareholders, flows | INF_DIARIO NR_COTST, CAPTC_DIA, RESG_DIA | same as NAV |
| Manager | registro_fundo.Gestor (71%) | ~71% (higher for active; not measured) |
| Administrator | registro_fundo.Administrador (71%) + CNPJ_Administrador | ~71% |
| Custodian | registro_classe.Custodiante (99%) | ~99% |
| Inception | registro_classe.Data_Inicio (100%) | ~100% (already loaded) |
| Category | registro_classe.Classificacao (72%) and Classificacao_Anbima (72%) | ~72% |
| Benchmark | registro_classe.Indicador_Desempenho (70%) | ~70% (text, not an ID) |
| Fees (admin, performance) | Lâmina (taxa de administração, performance, máxima, entrada/saída; UNVERIFIED headers) and legacy cad_fi TAXA_ADM/TAXA_PERFM | lâmina required for retail open funds only; est. 30-50% (UNVERIFIED) |
| Risk indicator | Lâmina risk scale / profile (UNVERIFIED) | same as lâmina |
| Status | registro_classe.Situacao (100%) | 100% |
| Currency | BRL (assume; foreign-currency classes rare) | 100% |
| Share class | registro_subclasse (ID_Subclasse, name) | all subclasses (10,720) |
| Holdings | CDA monthly (BLC files + fie/fiim) | funds that file public CDA; confidential positions hidden for a window |
| ISIN at security level | CDA position rows (field name UNVERIFIED) | partial, depends on asset type |
| Fund-level ISIN / ticker | NOT in CVM registry or inf_diario. B3 listed-fund list (FII, FIAGRO, ETF, FIDC listed) gives ticker (4-letter + 11) and ISIN; ANBIMA data.anbima.com.br shows "código ANBIMA/ISIN" per fund but API is credentialed | Realistically only listed funds: ~1,539 FII + 379 FIAGRO + 262 FIIM + some FIDC, i.e. ~6% of all classes. Open funds will mostly have no ISIN. |
| Distributions | FII/FIAGRO: CVM FII monthly (informe mensal) and B3 events (UNVERIFIED); FIF accumulate | FII/FIAGRO only |
| Manager/admin legal names | Receita Federal CNPJ base (razão social by CNPJ_Administrador / CPF_CNPJ_Gestor) | ~100% where CNPJ present |

### Concrete connector design (Brazil)
1. Replace `sync-cvm-holdings` start with a pre-flight: download `cda_fi_YYYYMM.zip` with a browser-grade User-Agent, list the zip members, log them, and fail loudly if none match expected names (do not reset `holdings_status` until rows exist). Run for the last 12 months (M-1..M-3 are refreshed daily by CVM per the prior notes) and keep `holdings_report_date`.
2. Parse by member name: `cda_fi_BLC_1..8_*.csv` (positions), `cda_fi_PL_*.csv` (net assets), `cda_fie_*.csv` / `cda_fiim_*.csv` (FIDC, FIAGRO, index funds; if the Nov 2025 rename is live; fall back to `cda_fiim_*`). Capture the real header of each member in `reports/cvm_cda_headers.json` first, then fix column mapping; join key `CNPJ_FUNDO_CLASSE` (+ `ID_SUBCLASSE`) to `funds.source_fund_id` (digits[:ID_SUBCLASSE]). Map to `portfolio_holdings` (security_name, isin, quantity, market_value) and weights to `holding_metrics`.
3. NAV: loop all months back to the target depth (e.g. 2020-01 onward; URL `INF_DIARIO/DADOS/inf_diario_fi_YYYYMM.zip`, and `HIST/` yearly zips for older, UNVERIFIED); write to `nav_observations` with `(source_fund_id=cnpj[:subclass], valuation_date, nav)`; store `VL_PATRIM_LIQ`, `NR_COTST` in a snapshot table or `fund_profile_snapshots`.
4. Registry enrichment (already partly done): also persist Gestor CPF/CNPJ (`CPF_CNPJ_GESTOR`), `CNPJ_Administrador`, `Custodiante`, `Classificacao_Anbima`, `Indicador_Desempenho`, `Forma_Condominio`, `Exclusivo`, `Publico_Alvo`, `Previdenciario` into `fund_profile_snapshots`.
5. Lâmina and perfil mensal: monthly ZIP, key `CNPJ_FUNDO_CLASSE` (UNVERIFIED), load fees and risk after confirming headers from `meta_lamina_fi_txt.zip`.
6. Tickers/ISIN: build a mapping table class CNPJ -> ticker/ISIN from B3 listed funds (get the endpoint from the browser dev tools on the B3 fund pages; terms unknown) and, if an ANBIMA developer agreement is signed, Feed de Fundos (client_id + token). Receita Federal CNPJ monthly dump for legal names.
7. Ops: one ZIP per month, no auth, no stated rate limit; CVM license ODbL per prior notes; Cloudflare may challenge cloud IPs, so keep the download host fixed, use sequential requests with delay, and cache by hash (manifest already exists).

### Inferences
- The shortest path to non-zero holdings is just running the existing importer once a month with correct member handling; the zero is an ops gap, not evidence that CDA lacks the data.
- Fund-level ISIN will stay near 6% for Brazil by design (only listed vehicles carry ISINs).
- The prior notes' claim that CVM files "may be keyed on CNPJ_FUNDO" is superseded: live sample already uses `CNPJ_FUNDO_CLASSE`.

### Gaps
- All /dados/FI/DOC/ listings and dataset pages: HTTP 403 (Cloudflare) from this host (URLs: https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/, .../CDA/META/, .../LAMINA/DADOS/, .../PERFIL_MENSAL/DADOS/, .../BALANCETE/DADOS/, .../EXTRATO/DADOS/, .../INF_DIARIO/DADOS/, https://dados.cvm.gov.br/dataset/fi-doc-cda). Manual verification for the project owner: (1) open https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/ in a normal browser and record the newest zip name; (2) download one zip and `unzip -l` it to list member names (BLC_*, PL, fie, fiim, CONFID); (3) `head -2` each member and paste headers into `reports/`; (4) repeat for LAMINA (`lamina_fi_AAAAMM.zip` + `META/meta_lamina_fi_txt.zip`), PERFIL_MENSAL and BALANCETE; (5) check https://dados.cvm.gov.br/pages/novidades for the exact rename dates; (6) if the ETL host is challenged, run the download from an allowed IP or ask CVM (dados.abertos@cvm.gov.br, UNVERIFIED address) to allowlist it.
- Real CDA/lâmina/perfil headers, current existence of `cda_fie_*`, fund-level ISIN presence in CDA: not seen.
- B3 listed-funds payload, B3 terms, Receita CNPJ file layout, robots.txt of dados.cvm.gov.br (blocked).
- CVM "26/01/2026" rename: not found; only the 2024 notice was found via snippet.

---

## 2. Russia (0 funds in DB)

### Takeaway
Russia has strong, free, official, machine-readable sources: the Bank of Russia unit-fund register (`list_PIF.xlsx`, 8,176 rows) and its new monthly data showcase (`mutual_fund_data.xlsx`, 673 funds with ISIN, fees, benchmark, returns), plus Moscow Exchange ISS JSON for exchange-listed units with ISIN, daily history and market data. Official fund NAV (SCHA) and per-unit calculated value are not exposed by ISS; they are published by each management company (and visible on MOEX web pages), so daily NAV history needs per-UK scraping or a UNOFFICIAL aggregator (Investfunds).

### Cited Findings
- Register of PIFs (VERIFIED, downloaded): `https://www.cbr.ru/vfs/finmarkets/files/supervision/list_PIF.xlsx` (1.77 MB, sheet `report_list`, title "Сведения о паевых инвестиционных фондах по состоянию на 17.11.2026"). Columns: № п/п, Тип, Статус, Полное название, Краткое название, Категория, Номер правил доверительного управления, Дата присвоения номера, Срок действия договора, Дата окончания формирования, "для квалифицированного инвестора", "могут обращаться на организованных торгах", неполная оплата, СД согласованы, Все предыдущие названия, изменения правил, УК (name, OGRN), Специализированный депозитарий (name, OGRN), Регистратор (name, OGRN), Прекращение/исключение (date, reason). No ISIN, no INN of the UK. 8,176 rows: 4,151 excluded; 3,744 formed; 163 forming; 103 being wound up; 10 agreed; 2 formation expired. Active (non-excluded) 4,025: closed (Закрытый) 3,461, open 265, interval 177, exchange-traded (Биржевой) 122; 3,340 flagged for qualified investors only. — [Bank of Russia file](https://www.cbr.ru/vfs/finmarkets/files/supervision/list_PIF.xlsx)
- Data showcase (VERIFIED, downloaded): page `https://www.cbr.ru/RSCI/data_showcase/` (launched 11 June 2026 per search summary), file `https://www.cbr.ru/Content/Document/File/193443/mutual_fund_data.xlsx` (837 KB, 6 monthly sheets named `Витрина_ПИФ_30 09 2026` ... `30 04 2026`, 673 data rows in the latest). The page states it covers funds accessible to non-qualified investors, data from trust-management rules and reporting, "носят ознакомительный характер", updated monthly. Columns (25): rules number; fund name; ISIN of units; fund type; category; status; UK name; UK INN; UK website; date of current rules edition (Excel serial); strategy type active/passive; benchmark/indicator; permitted tracking deviation; UK fee; performance fee; infrastructure fee; maximum total expenses; right to income; payout frequency; entry load; exit discount; return 1m, 3m, 6m, 12m (decimal fractions). Sample row: rules 0007, "ОПИФ рыночных финансовых инструментов «Первая – Фонд Рублевые сбережения»", ISIN RU000A0EQ3Q5, benchmark RUCBTRNS, fee "1,5% от среднегодовой СЧА". Latest sheet: 673 funds (closed 282, open 259, exchange-traded 118, interval 11), 570 with ISIN; 646 formed, 24 in termination. — [Showcase page](https://www.cbr.ru/RSCI/data_showcase/), file above
- The Bank of Russia statistics page lists quarterly aggregate balance-sheet workbooks (`main_indicators_balance_sheet_2026_2.xlsx` etc.) at `https://www.cbr.ru/statistics/rsci/`; they are aggregates, not per-fund. — [CBR statistics](https://www.cbr.ru/statistics/rsci/)
- List of management company licences: `https://www.cbr.ru/vfs/finmarkets/files/supervision/list_managementcompanies.xlsx` (172 KB, 200). Layout not inspected. — [CBR registries](https://www.cbr.ru/registries/RSCI/)
- cbr.ru robots.txt (VERIFIED) disallows only /search/ and a few specific PDFs. A search snippet says the showcase runs in "test mode" and feedback goes to bd_pif@cbr.ru (investfunds.ru news, UNOFFICIAL, date not confirmed). — [CBR robots](https://www.cbr.ru/robots.txt), [Investfunds news](https://investfunds.ru/news/172227/)
- MOEX ISS (VERIFIED, no auth, JSON, 200): the ISS answers e.g. `https://iss.moex.com/iss/securities/TMOS.json?iss.meta=off` with description rows: SECID TMOS, NAME "БПИФ Т-КАПИТАЛ ИНДЕКС МОСБИРЖИ", REGNUMBER 4100, ISIN RU000A101X76, ISSUEDATE (start of trading) 2020-08-26, LISTLEVEL 1, REGISTRY_DATE 2020-07-13, TYPE exchange_ppif, GROUPNAME "Паи ПИФов", EMITTER_ID, etc. — [ISS TMOS](https://iss.moex.com/iss/securities/TMOS.json?iss.meta=off)
- ISS securities list by group (VERIFIED): `https://iss.moex.com/iss/securities.json?iss.meta=off&group_by=group&group_by_filter=stock_ppif&limit=100&start=N&securities.columns=secid,shortname,regnumber,isin,emitent_title,type,primary_boardid,is_traded` pages 100 at a time and returned 1,000 distinct SECIDs through start=900 (stopped there, total not confirmed). Types: exchange_ppif (BPIF) 184 of the first 1,000 (121 traded), public_ppif (OPIF) 233, private_ppif 499, interval_ppif 84 (traded flag counts in sample: exchange 121 traded/63 not; public 45/188; private 82/417; interval 42/42). `group_by_filter=stock_etf` returned 54 foreign-wrapper ETFs (type etf_ppif, e.g. CSX5-RM with ISIN IE00B53L3W79, KWEB-RM US5007673065), which are non-Russian-domiciled (BlackRock, Krane) and are not Russian funds.
- ISS history (VERIFIED): `https://iss.moex.com/iss/history/engines/stock/markets/shares/boards/TQBR/securities/TMOS.json?iss.meta=off&iss.only=history&history.columns=TRADEDATE,CLOSE&from=2026-11-01` returned closes through 2026-11-16 (e.g. `["2026-11-02",6.19]`). TMOS primary board is TQBR; board TQTF also lists it, but the history call on TQTF with `from=2026-11-10` returned empty while `from=2025-01-01` returned data starting 2025-01-03, so always use the primary board and test emptiness. These are exchange CLOSE prices, not NAV.
- ISS marketdata (VERIFIED): `https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/TMOS.json?iss.only=marketdata` returned 55 columns including LAST, WAPRICE, VOLTODAY, ETFSETTLEPRICE (null in sample), ISSUECAPITALIZATION (null), TRADINGSTATUS. `securities` block includes PREVPRICE, LOTSIZE, FACEVALUE, ISIN, REGNUMBER, CURRENCYID (SUR), ISSUESIZE (0). So ISS does not give NAV/SCHA for TMOS in these fields. `ISSUECAPITALIZATION` null. — [ISS marketdata](https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/TMOS.json?iss.only=marketdata)
- Search results say MOEX fund cards (`https://www.moex.com/ru/funds/bpif/tmos`) show NAV (СЧА) and unit-price dynamics with 15-minute delay, but I found no ISS endpoint for NAV; commercial NAV API exists at cbonds.ru (UNOFFICIAL, paid). My direct fetch of the moex.com fund page timed out. — [MOEX fund card example](https://www.moex.com/ru/funds/bpif/aiiq), [Cbonds API](https://cbonds.ru/api/etf/)
- ISS robots: `https://iss.moex.com/robots.txt` returned `User-agent: * Disallow: /` (VERIFIED). The ISS free tier is delayed data meant for personal/non-commercial use; redistribution needs a MOEX licence (UNVERIFIED; check https://www.moex.com/a2193 terms). Mention to owner: robots disallow applies to crawlers; ISS is an API with documented public endpoints, but confirm terms before scheduled bulk use.
- NAUFOR (UNOFFICIAL self-regulatory association; reachable, 200, windows-1251, robots.txt returned a 404). Site menus include "Раскрытие информации", "Для управляющих компаний ПИФ". Market statistics files exist (`getfile.asp?id=19325` appeared in search) but not inspected. — [NAUFOR](https://naufor.ru/)
- NAV publication duty: Russian management companies must publish on their sites the SCHA and unit calculated value (расчётная стоимость инвестиционного пая) for each calculation date; open funds daily. I could not fetch the legal text this session (UNVERIFIED); source of truth is each UK website and, for exchange-traded units, MOEX card pages.
- Investfunds (investfunds.ru) is an UNOFFICIAL aggregator with per-fund NAV/unit price pages; terms not reviewed. — [Investfunds example](https://investfunds.ru/funds/13853/)
- Sanctions/access (factual, UNVERIFIED legal conclusion): MOEX, the National Settlement Depository and Russian managers are subject to US/EU/UK sanctions regimes in several forms; fund managers are Russian entities. The data sources above are public websites and downloading public regulatory data is generally not itself a prohibited transaction, but commercial redistribution, paid licensing from MOEX/Cbonds, or any payment to listed entities should go through legal/compliance review. Also expect geo-blocking of foreign IPs (Bank of Russia site responded from this host; MOEX ISS responded from this host).

### Field-by-field matrix (Russia)
| Field | Best official source | Expected fill |
|---|---|---|
| Fund list, status, type, category | CBR `list_PIF.xlsx` (4,025 non-excluded; ~700 retail-visible) | 100% |
| Rules number (stable ID) | list_PIF `Номер правил` / showcase col 1 / ISS `REGNUMBER` | 100%; join key for all three |
| ISIN | Showcase (570 of 673) and ISS `ISIN` for listed units | ~85% of showcase funds; ~100% exchange-traded; lower for closed/private |
| Ticker | ISS `SECID` | listed units only (~184 BPIF in first 1,000 + open/interval/closed listed) |
| Manager (name) | list_PIF UK name + OGRN; showcase UK name + INN | ~100% |
| Administrator/custodian | list_PIF specialized depository and registrar (name, OGRN) | ~100% |
| Inception | list_PIF `Дата присвоения номера` (rules registration date) and `Дата окончания формирования` (formation end); ISS `ISSUEDATE` (start of trading) | ~100% (rules date, not strictly first NAV) |
| Category | list_PIF `Категория`; showcase `Категория фонда` | 100% |
| Benchmark | Showcase col 12 | ~50-60% of 673 (UNVERIFIED count) |
| Fees / TER | Showcase cols 14-17 (text, "% от среднегодовой СЧА") | ~100% of showcase funds; text must be parsed |
| Risk indicator | Not in these files; each fund's KID/investor memo (UK site) | missing |
| Distributions | Showcase `Право на доход`, `Периодичность выплаты` (policy); amounts from UK site | policy only |
| Daily NAV, NAV history | UK websites (statutory daily SCHA/unit value) and MOEX card pages; no bulk official file found | needs per-UK scraping; exchange price history from ISS free |
| Net assets (SCHA) | UK websites, quarterly CBR aggregates only | missing in bulk |
| Holdings | UK periodic reports; not found centralised | missing |
| Status | list_PIF `Статус`, `Основание прекращения` | 100% |
| Returns | showcase 1/3/6/12m | for funds old enough |
| Currency | RUB (ISS CURRENCYID SUR for listed) | 100% |

### Concrete connector design (Russia)
1. Source A `ru_cbr_pif_register`: GET `list_PIF.xlsx`, parse sheet `report_list`, header row index 3 (row 1 title, row 2 group labels, then data from row 4; 8,176 rows). Upsert into `funds` with `source_fund_id = rules number` (e.g. `0001-44504664`), name, UK, depositary, registrar, status, type, category, qualified-only flag, formation dates; exclude `Исключён из реестра` by default or mark `status=excluded`.
2. Source B `ru_cbr_showcase`: GET `mutual_fund_data.xlsx` (new `Document/File/<id>` on every monthly publish, so scrape the link from `/RSCI/data_showcase/`), first sheet is the newest month; join by rules number; load ISIN, benchmark, fee text, performance, 1-12m returns into `fund_profile_snapshots`; convert the Excel serial date for rules edition.
3. Source C `ru_moex_iss`: page `securities.json` with `group_by=group&group_by_filter=stock_ppif`, then per SECID `/iss/securities/{SECID}.json` for REGNUMBER/ISIN/ISSUEDATE and `/iss/history/engines/stock/markets/shares/boards/{PRIMARY_BOARD}/securities/{SECID}.json?from=...` (default 100 rows per page, use `history.cursor`) for exchange prices; map to `nav_observations` only if flagged `price_type=exchange_close` (it is not NAV). Match to registry via REGNUMBER (ISS) = rules number numeric part (e.g. ISS 4100 vs registry `4100-...`).
4. NAV Phase 2: pick the top ~30 managers by fund count (UK names come from list_PIF), write one adapter per UK site for SCHA and unit calculated value; keep UNOFFICIAL aggregator (Investfunds) only as flagged fallback.
5. Rate/etiquette: ISS has no published key; keep to a few requests per second, cache static lists weekly, run history daily after 21:00 Moscow. Check MOEX terms before production.

### Inferences
- The CBR register plus showcase give Russia identity, status, manager, depositary, ISIN, fees, benchmark and returns for ~670 retail funds at no cost, which is better than what most countries provide officially. The gap is daily NAV and holdings.
- Rules number is the cross-source key; ISIN joins ISS to showcase.

### Gaps
- No official bulk NAV/SCHA file found (CBR or MOEX ISS); moex.com card page fetch timed out; the NAV-disclosure statute and CBR reporting forms not read.
- ISS total number of PPIF securities (more than 1,000 not enumerated); ISS licensing terms not read; NAUFOR data files not inspected; list_managementcompanies.xlsx layout not inspected.
- Current legal effect of sanctions on a given usage is not verified; needs counsel.

---

## 3. South Africa (1,945 funds, name only)

### Takeaway
The only free official bulk source found is the ASISA quarterly CIS fund list, already integrated, but the connector keeps only code and name and throws away sector, fund type, FoF and ETF flags that are in the same file. No free official bulk NAV, holdings, TER or ISIN source exists; JSE is behind a WAF (403) and FSCA has only an interactive search. Daily prices come from each manager's website (per-fund pages; M&G offers a 12-month all-funds price download) or commercial vendors (Profile, Sharenet, Morningstar).

### Cited Findings
- Integrated ASISA file (VERIFIED from repo raw file `data/raw/south_africa/asisa_cis_fund_list_20260630.xlsx`, URL `https://www.asisa.org.za/media/jf5m4adc/list-of-cis-as-at-30-june-2026.xlsx`): sheet `CISFunds`, row 1 `Quarter: 30/Jun/2026`, header row 3: `Fund Code | Fund Name | Sector Code | Sector Name | Fund Type | FoF | Third Party Fund | Third Party Manager | ETF`. Sample: `MCEFA1 | Mazi BCI Equity Fund | DEGN | South African – Equity – General | Retail | No | Yes | N/A | No`. 1,951 data rows. Fund Type: Retail 1,748, Institutional 197. Top sectors: SA Multi Asset High Equity 286, Global Equity General 188, SA Multi Asset Low Equity 179, SA Equity General 172. The `Sector Code` first letter encodes domicile family (D = domestic, W = worldwide, G/F/etc. UNVERIFIED mapping).
- Connector `app/connectors/asisa.py` (code read): reads only `Fund Code` and `Fund Name`, sets `currency=None`, `isin=None`; discards Sector Code/Name (category), Fund Type (retail/institutional, share-class audience), FoF, Third-Party Fund/Manager (white-label manager) and ETF flag. License status is "Unknown". The URL has a hash-like media path that changes each quarter (`jf5m4adc`), so the quarterly refresh needs link scraping from `https://www.asisa.org.za/statistics/`.
- ASISA headline statistics: 1,945 local CIS portfolios at 30 June 2026 and 800 foreign-currency ones (prior notes; not re-fetched). ASISA robots.txt carries Cloudflare "content signals" (search/ai-input/ai-train), a reservation of rights under EU copyright directive Article 4; the lines that follow the comment header were not seen as `Allow/Disallow` (only the header was printed), so terms for automated use are to be confirmed. — [ASISA robots](https://www.asisa.org.za/robots.txt), [ASISA stats page](https://www.asisa.org.za/statistics/)
- FSCA (VERIFIED reachable): `https://www.fsca.co.za/Regulated-Entities/` offers "Collective Investment Schemes" via an interactive search (`/Entity-Persons-Search?iframe_target=cis-management` behind an "Accept and Continue" gate) and document downloads from its own API (`/_api/cr3ad_regulatedentitiesdocuments(...)`); no bulk register of CIS portfolios was found, and I did not drive the interactive search. robots.txt is a stub ("marker file generated by the precompilation tool"). Statute requires managers to file portfolio holdings quarterly to the registrar within 30 days (2003 notice) but publication of that data was not found. — [FSCA regulated entities](https://www.fsca.co.za/Regulated-Entities/), [CISCA notice 2003](https://www.gov.za/sites/default/files/gcis_document/201409/24984a0.pdf)
- JSE: `https://www.jse.co.za/` and `https://www.jse.co.za/services/market-data/exchange-traded-products` returned HTTP 403 (WAF) to ordinary curl. Not bypassed. Search could not find an official ETP list/NAV download; a 2021 JSE ETF factsheet PDF shows historic daily creations/redemptions publication. Manual steps for the owner: open the JSE ETP page in a browser, look for an "ETF/ETN list" or "Daily NAV" Excel, note ISIN/alpha code columns, and check the JSE market-data licence (historical/NAV data is a paid product, UNVERIFIED). — [JSE ETF factsheet Jan 2021](https://www.jse.co.za/sites/default/files/media/documents/2021-03/JSE%20ETF%20Factsheet%20-%20January%202021.pdf)
- etfSA (UNOFFICIAL industry site) publishes monthly ETP statistics PDFs (June 2026 total ETP market cap R308,115m) and a third-party GitHub JSON of ETFs (tickers, categories, no ISIN/NAV) exists. — [etfSA research](https://www.etfsa.co.za/research.htm), [FAnews ETFSA report](https://www.fanews.co.za/assets/Marilyn_2026/21062026ETFSA.pdf)
- Manager price pages (search snippets, UNVERIFIED format): M&G offers a download of all fund prices for the past 12 months, refreshed by 18h00 daily; Hollard has daily prices with a historic section; Stanlib offers distribution-breakdown downloads per fund; Sanlam and Allan Gray publish prices as web tables. Coronation redirected my request to a welcome/consent page; Satrix, Ninety One, Old Mutual, Sanlam returned 301 redirects; Allan Gray fund-prices paths returned 404 (a different URL exists: https://allangray.co.za/what-we-offer/unit-trusts). Whether any publishes a documented CSV/API was not confirmed. — [M&G prices](https://mandg.co.za/personal-investor/our-funds/all-funds/prices), [Hollard daily prices](https://hollard.co.za/investments/flexible-savings/fund-centre/daily-prices-embed), [Sanlam daily prices](https://www.sanlamonline.co.za/investment/daily-prices-and-fund-values)
- Commercial vendors (UNOFFICIAL): Profile Media FundsData (feeds in CSV/XML/JSON, daily unconfirmed and next-morning confirmed price sets), Sharenet Daily Download (subscription), Morningstar. — [Profile FundsData](https://profile.co.za/unit-trusts-data/fundsdata/)
- Prudential Authority: regulates banks/insurers, not CIS; no fund data found (not investigated deeply).

### Field-by-field matrix (South Africa)
| Field | Best official source | Expected fill |
|---|---|---|
| Fund code, name | ASISA list (already) | 100% of ~1,945-1,951 |
| Category | ASISA `Sector Code/Name` (in the same file, not yet loaded) | 100% |
| Share class / audience | ASISA `Fund Type` retail/institutional, FoF flag, `ETF` flag, third-party manager | 100% (class-level detail absent; ASISA is per portfolio) |
| Currency | Derive from sector prefix (D = ZAR domestic, W/G/F = foreign-currency-denominated mandate; UNVERIFIED rule) or manager factsheet | ~100% inferred ZAR for domestic; rest per factsheet |
| Manager | ASISA list does not name the management company; fund code prefix (e.g. MCEFA1) maps to manager only by convention; FSCA register has manager names but interactive only | missing (0% in bulk today) |
| Admin/custodian/trustee | FSCA register / manager factsheets | missing |
| ISIN | JSE (ETFs), manager factsheets; no official unit-trust ISIN list | ETFs only (~100+ listed ETPs, JSE 403); unit trusts largely missing |
| Ticker | JSE alpha code for ETFs; unit trusts have none | ETFs only |
| NAV daily + history | Manager websites; vendors | per-manager scraping; nothing bulk official |
| Net assets, TER/fees | ASISA TER publications (UNVERIFIED), manager MDDs/factsheets, ASISA standard TER disclosure | not found in bulk |
| Holdings | Manager quarterly portfolio disclosures (statutory) | PDF/web per manager |
| Inception | Manager factsheets | not in bulk |
| Distributions | Stanlib/other manager distribution downloads | per manager |
| Risk indicator | Manager MDD (risk profile) | per manager |
| Status | ASISA presence in list = active | 100% (derived) |

### Concrete connector design (South Africa)
1. Extend `asisa.py` to read all 9 columns: category = `Sector Name`, `sector_code` into `fund_profile_snapshots`, `fund_type` (Retail/Institutional), `is_fof`, `is_etf`, `third_party_manager`; discover each quarter's file by scraping `https://www.asisa.org.za/statistics/` for `list-of-cis-as-at-*.xlsx` (the `media/<hash>/` segment changes); keep history by `Quarter:` cell.
2. Add a manager-adapter framework (priority by AUM): M&G (12-month all-funds price download, UNVERIFIED columns), Hollard, Stanlib, Sanlam, Allan Gray, Coronation, Ninety One, Old Mutual, Satrix (ETFs/index unit trusts). Each adapter outputs (fund name, class, date, price, currency, distribution) and is fuzzy-matched to ASISA `Fund Name` (names are quirky with leading spaces) with manual review for ambiguities; label `data_source=manager_site` (official publisher of own prices, but not an authority).
3. JSE ETF adapter once access is verified manually: ETP list (ISIN, alpha code, issuer) and daily NAV file; join to ASISA rows flagged `ETF=Yes`.
4. FSCA: do not automate the interactive search; only record the register URL and ask FSCA for a bulk extract (PAIA/open-data request).

### Inferences
- Expect ZA to stay a thin country: identity+category quickly, price coverage only as fast as manager adapters are built; official ISIN/ticker/fees in bulk are unlikely.
- Name matching, not a shared ID, will join ASISA to manager price files.

### Gaps
- ASISA robots Allow/Disallow lines, quarterly TER/fund-level statistics availability, terms of use.
- JSE ETP/NAV file locations and licence (403).
- Any documented CSV/API from Allan Gray, Coronation, Ninety One, Satrix, Old Mutual (only redirects/404s seen; no price-file URLs verified).
- FSCA bulk register; Prudential Authority data; ZAR/foreign currency rule from sector code.

---

## 4. Cross-cutting: bulk vs per-fund, auth, limits, language, reachability

### Takeaway
All three countries rely on bulk files (CVM zips, CBR xlsx, ASISA xlsx) for identity and on per-security/per-manager calls for NAV/prices (MOEX ISS per SECID; ZA manager sites).

### Cited Findings
| Source | Bulk/per-fund | Auth | Rate limit | Terms/robots | Language | Reachability from this host |
|---|---|---|---|---|---|---|
| CVM dados abertos | bulk monthly zips | none | none stated | ODbL per prior notes; robots not seen (403) | Portuguese, CSV latin-1, `;` separated | 403 now (worked 2026-10-18 from project run) |
| BCB SGS | per-series JSON | none | not stated | public API | Portuguese | OK |
| ANBIMA data/API | per-fund pages; API credentialed | client_id + token | per contract | robots disallows some service paths | Portuguese | UI OK, API 401 |
| B3 listed funds | endpoint (undocumented) | none | unknown | unknown | Portuguese | 200 but payload unknown |
| Receita CNPJ | monthly bulk zip | none | n/a | public | Portuguese | host OK |
| CBR (register, showcase) | bulk xlsx | none | none stated | robots permissive | Russian (EN pages exist) | OK |
| MOEX ISS | per-SECID JSON + paged lists | none (free, delayed) | not published | robots `Disallow: /`; licence for redistribution | Russian field titles, English columns | OK |
| NAUFOR | pages/files | none | n/a | UNOFFICIAL association; robots 404 | Russian | OK |
| ASISA | bulk quarterly xlsx | none | n/a | content-signal reservation | English | OK |
| FSCA | interactive search | none, accept gate | n/a | not read | English | OK |
| JSE | web pages/data products | n/a | n/a | commercial data licence | English | 403 |

### Inferences
- Two of the three highest-value sources for this task (CVM and JSE) challenge this host; run them from the ETL host or a browser and keep manifest hashes.

### Gaps
- No rate limits are documented by any source above; apply conservative sequential fetching.
