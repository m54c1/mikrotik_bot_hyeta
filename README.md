крч это бот для ограничения доступа к инету одной(или не одной) из железок. 
суть в том, что в ip/firewall/nat стоит на 3(поменяйте на своё) номере правило srcnat accept, которое служит рубильником, чтобы дальше этот айпи не маскарадился. 
вот такая вот примитивная рабочая стратегия. не делал с поиском по комменту, потому что эта хуйня нормально не может вывод отправить через api, в итоге только по номерам да и пох

создайте группу с доступом к api,write,read,test
потом нового юзера создаёте в данной группе, в ip/services дайте доступ к api с айпи тачки, на которой будет эта хуйня крутится в докере, либо api-ssl, если тачка будет не в локалке.

эта хуйня может работать через прокси. в переменных указываете адрес в формате PROXY=http://10.50.10.2:7890 // socks5://

скрипты для самого микротика

    /system script
    add name=inet_off_250 policy=read,write,test source={
    :local ip "10.254.0.250"
    
    /ip firewall nat set numbers=2 disabled=no

    /ip firewall connection remove [find \
        src-address=$ip \
        or dst-address=$ip \
        or reply-src-address=$ip \
        or reply-dst-address=$ip \
    ]
    }

    /system script
    add name=inet_on_250 policy=read,write,test source={
    /ip firewall nat set numbers=2 disabled=yes
    }

бля нахуя я вообще всё это пишу. надеюсь, что этот репозиторий никто не увидит и мне не будет стыдно за оформление и нецензурную лексику
