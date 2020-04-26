require "rubygems"
require "mechanize"

support_section_urls = File.open("./temp/individual_articles.txt", "r").readlines
support_section_urls = support_section_urls.reject(&:empty?)
support_section_urls = support_section_urls.map {|x| x.chomp}

agent = Mechanize.new

articles = []

support_section_urls.each do |sec|
    page = agent.get(sec)
    #h1.page-header
    body = page.body
    doc = Nokogiri::HTML(body)
    title = doc.css("h1.page-header")[0].text
    articles.push sec + "\t" + title
end


File.open("temp/urls_with_titles.txt", "w") do |f|
    articles.each do |art|
        f.puts art
    end
end
