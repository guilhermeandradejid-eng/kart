# Turbo Turma — Documento de Design (MVP)

## Visão
Kart arcade colorido, rápido e "suculento" (muito *game feel*), com uma turma de bichos brasileiros.
Referências: Mario Kart 8 (drift/mini-turbo, itens, customização), Crash Team Racing (pistas com
saltos, personalidade exagerada), Diddy Kong Racing (pistas temáticas tropicais).

## Pilares
1. **Pilotar é gostoso desde o primeiro segundo** — curvas responsivas, drift com recompensa clara
   (cores das faíscas), batidas que não frustram (o kart desliza na parede, não para).
2. **Tudo reage** — kart, piloto, câmera, partículas, som e HUD respondem a cada evento.
3. **Personagens com alma** — animação seguindo os 12 princípios + física secundária.
4. **Customização com consequência** — cada peça muda a sensação e os atributos.

## Loop da corrida
Apresentação (sobrevoo) → contagem com largada-foguete → 3 voltas → chegada (câmera lenta, confete,
pódio) → resultados → correr de novo / menu.

## Física (valores de referência)
| Parâmetro | Valor |
|---|---|
| Velocidade máx. | 25,5 + 1,05 × atributo (m/s) × categoria (50cc 0,86 · 100cc 0,95 · 150cc 1,04) |
| Aceleração | ~90% da máx. em 3,1 − 0,28 × atributo s |
| Esterço | 1,75 + 0,11 × manobra (rad/s), reduzido em baixa e altíssima velocidade |
| Drift | yaw = dir × esterço × (0,46 + 0,44 × entrada para dentro) — raio ~14 m (fechado) a reto (aberto) |
| Mini-turbo | níveis em 0,85 / 1,8 / 3,0 s de carga → 0,7 / 1,15 / 1,7 s de boost × atributo |
| Boost | +32% na velocidade máxima, ignora penalidade de fora-de-pista |
| Fora de pista | 50% + 4,5% × tração da velocidade |
| Gravidade | 34 m/s² (0,68× em saltos de rampa) |

## Itens
| Item | Efeito | Distribuição |
|---|---|---|
| Pimenta | turbo de 1,7 s | mais comum no fundo do pelotão |
| Casca de banana | armadilha atrás; spin-out de 1,25 s | mais comum na frente |
| Coco-bomba | arremesso que segue a pista, quica e explode (raio 5,5 m) | meio do pelotão |

Conchas douradas: +1,2% de velocidade máx. cada (máx. 10), perde 3 ao ser atingido.

## IA
Linha de corrida pré-calculada a partir da curvatura (ápice por dentro, entrada por fora), viés de
faixa por piloto, *look-ahead* proporcional à velocidade, velocidade segura v = √(a/κ), drift apenas
em curvas consistentes de mesmo sentido, desvio de perigos/karts, uso de itens por contexto,
watchdog de progresso (ré → respawn), *rubber band* leve (+10% atrás / −7% muito à frente).

## Arte
Estilo "brinquedo" de formas suaves (modelagem SDF), cores saturadas por vértice, PBR leve com
clearcoat no kart, *rim light* na pelagem, céu tropical com nuvens procedurais, AgX + glow + SSAO.

## Áudio
Todo sintetizado: motor em 3 camadas por rpm, vozes por síntese de formantes, músicas brasileiras
(baião/samba-rock 140 BPM, versão volta final 150 BPM, bossa nova no menu).
