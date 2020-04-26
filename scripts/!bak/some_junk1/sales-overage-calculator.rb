#!/usr/bin/ruby

require "rubygems"
require "json"
require "faraday"
require "csv"
require "google/apis/drive_v3"
require "googleauth"
require "googleauth/stores/file_token_store"
require "fileutils"

Drive = Google::Apis::DriveV3 # Alias the module
drive = Drive::DriveService.new
drive.get_file("1gGSCURCWTbMrI9_KxhAhxJcIqxdvtSurYK9CRFo3EBY", download_dest: '/scripts/sales-overage-calculator/temp.csv')


file_id = '1gGSCURCWTbMrI9_KxhAhxJcIqxdvtSurYK9CRFo3EBY'
#content = drive_service.export_file(file_id, 'text/csv')