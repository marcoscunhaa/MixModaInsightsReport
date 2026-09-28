from dataclasses import dataclass
from datetime import date
@dataclass
class AnalysisConfig:
    loja:str
    data_inicio:date
    data_fim:date
    estoque_path:str
    vendas_path:str
    estoque_critico:float=1
    estoque_baixo:float=3
    cobertura_risco:float=1.5
    excesso_cobertura:float=6.0
