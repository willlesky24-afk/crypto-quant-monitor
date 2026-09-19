\# 📊 Crypto Quant Monitor



\## Descripción



Crypto Quant Monitor es un sistema de análisis cuantitativo de mercados diseñado para interpretar datos de criptomonedas mediante indicadores técnicos, análisis de volumen, evaluación de riesgo y generación de decisiones inteligentes.



El objetivo del proyecto es evolucionar hacia un motor cuantitativo capaz de analizar condiciones de mercado, almacenar históricos de señales y posteriormente realizar backtesting y evaluación estadística.



\---



\# 🚀 Versión actual



\## v1.6 — Signal History



Estado:



✅ Motor analítico funcional  

✅ Sistema de señales  

✅ Gestión de riesgo  

✅ Sistema de decisión  

✅ Scoring cuantitativo  

✅ Historial de señales  



\---



\# 🏗️ Arquitectura del sistema



```text

&#x20;                   Binance API

&#x20;                        |

&#x20;                        v



&#x20;                Data Loader



&#x20;                        |

&#x20;                        v



&#x20;             Technical Indicators



&#x20;                        |

&#x20;                        v



&#x20;              Volume Profile



&#x20;             POC / VAH / VAL



&#x20;                        |

&#x20;                        v



&#x20;                 Market Engine



&#x20;                        |

&#x20;         --------------------------------



&#x20;         |              |              |



&#x20;         v              v              v



&#x20;     Analyzer     Alert Engine   Signal Engine





&#x20;                        |



&#x20;                        v



&#x20;                   Risk Engine





&#x20;                        |



&#x20;                        v



&#x20;                Decision Engine





&#x20;                        |



&#x20;                        v



&#x20;                 Quant Score





&#x20;                        |



&#x20;                        v



&#x20;                   Report Layer





&#x20;                        |



&#x20;         ----------------------------



&#x20;         |                          |



&#x20;         v                          v



&#x20;  Streamlit Dashboard        Signal History





&#x20;                                     |



&#x20;                                     v



&#x20;                               SQLite Database

