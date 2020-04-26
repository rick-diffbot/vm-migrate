require "rubygems"
require "mechanize"

support_section_urls = File.open("./temp/support_section_urls.txt", "r").readlines
support_section_urls = support_section_urls.reject(&:empty?)
support_section_urls = support_section_urls.map {|x| x.chomp}

agent = Mechanize.new

articles = []

suffixes = []

support_section_urls.each do |sec|
    page = agent.get(sec)
    url_suffix = agent.page.uri.request_uri
    suffixes.push url_suffix
end

support_section_urls.each do |sec|
    page = agent.get(sec)
    links = page.links
    links.each do |link|
        href = link.href
        articles.push href
    end
end

File.open("temp/individual_articles.txt", "w") do |f|
    articles.each do |art|
        f.puts art
    end
end
