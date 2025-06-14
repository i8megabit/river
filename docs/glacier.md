# Glacier

Glacier — автономный агент. Он наблюдает сеть в Catchment, записывает события и раз в Melt Cycle создаёт Melt. Melt — обычный HTML отчёт, который позже разбирает River.

Основные шаги:
1. Сбор NetFlow v9 или похожих данных.
2. Хранение локально до конца цикла.
3. Формирование Melt и загрузка в S3.

Все внутренние логи можно найти в Ice Core.

[Глоссарий](./glossary.md)

| Термин | Значение |
|--------|----------|
| **River** | Центральная веб-платформа, куда стекаются данные. |
| **Glacier** | Автономный агент, собирающий сетевую статистику в локальной среде (Catchment) и отправляющий отчёт в виде Melt. |
| **Melt** | Единичный отчёт, сформированный Glacier и сброшенный в хранилище. |
| **Melt Cycle** | Цикл накопления и сброса отчёта Glacier. |
| **Catchment** | Локальная среда, где Glacier наблюдает сетевой поток. |
| **Delta View** | Экран River для просмотра изменений в трафике. |
| **Flow Ingestion** | Процесс приёма Melt-файлов платформой River. |
| **Ice Core** | Лог внутреннего состояния Glacier (опционально). |

