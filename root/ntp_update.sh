#!/bin/bash
/etc/init.d/ntp stop
ntpd -gq
/etc/init.d/ntp start
