# Исследование сетевого трафика и DDoS-атак в SDN с использованием RUNOS 2.0

**Описание проекта**
Данный проект представляет собой исследовательскую платформу для анализа сетевого трафика и моделирования DDoS-атак в программно-конфигурируемых сетях (SDN) с использованием контроллера RUNOS 2.0.

Приложения:

Host Manager (https://github.com/ARCCN/host-manager)  - преобразование IP-адресов в (коммутатор, порт)

Learning Switch (https://github.com/ARCCN/l2-learning-switch) - маршрутизация пакетов

*Для сборки и запуска программной реализации необходима виртуальная машина с установленно OS Ubuntu версии 22.10.*

Сборка:

1) Скачать и установить RUNOS 2.0 по инструкции (https://arccn.github.io/runos/docs-2.0/eng/11_RUNOS_InstallationGuide.html)
2) Скачать и установить эмулятор сети Mininet при помощи команды "sudo apt install mininet"
3) Поместить в директорию src/apps корневой директории RUNOS приложение Host Manager (https://github.com/ARCCN/host-manager)
4) Поместить в директорию src/apps корневой директории RUNOS папки "l2-learning-switch",  из репозитория с исходниками программной реализации (https://github.com/ARCCN/l2-learning-switch)
5) Собрать контроллер RUNOS 2.0 при помощи последовательности команд:
  - cmake ..
  - make
  
Запуск экспериментов:
1) Скачать папку "generation_dataset" из репозитория с исходниками программной реализации
2) Запустить контроллер RUNOS 2.0 при помощи команды "build/runos", выполненной из корневой директории runos
3) Базовый запуск программы "python3 generation_dataset.py"
4) Запуск с расширенными параметрами:
"sudo python3 generation_dataset.py \
    --hosts <количество_хостов> \
    --topo <linear|ring|star> \
    --duration <секунды> \
    --attack_prob <вероятность> \
    --output <файл.csv>"
