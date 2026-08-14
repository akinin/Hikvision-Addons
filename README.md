# Hikvision для Home Assistant

Персональный репозиторий защищённой версии приложения **Hikvision Домофон**.

## Установка

1. В Home Assistant откройте **Настройки → Приложения → Магазин приложений**.
2. Откройте меню **Репозитории**.
3. Добавьте `https://github.com/akinin/Hikvision-Addons`.
4. Установите приложение **Hikvision Домофон**.
5. На вкладке **Конфигурация** добавьте домофон и запустите приложение.

[![Добавить репозиторий в Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fakinin%2FHikvision-Addons)

## Что изменено

- удалён полный доступ к хосту и API Home Assistant;
- оставлено только необходимое подключение каталога `/media`;
- удалена устаревшая архитектура i386;
- обновлены зависимости с известными уязвимостями;
- секреты и чувствительные команды не выводятся в журнал;
- добавлена русская конфигурация и скрытые поля паролей;
- репозиторий содержит только стабильное приложение без отдельной beta-карточки.

Документация приложения: [doorbell/DOCS.md](doorbell/DOCS.md).

Исходный проект: [pergolafabio/Hikvision-Addons](https://github.com/pergolafabio/Hikvision-Addons).
