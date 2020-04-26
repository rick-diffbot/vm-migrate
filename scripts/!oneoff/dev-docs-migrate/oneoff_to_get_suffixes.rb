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
    links = page.links
    page.links.each do |link|
        href = link.href
        if href.include? "http"
            agent.get(href)
            url_suffix = agent.page.uri.request_uri
            suffixes.push url_suffix
        end
    end
end

File.open("temp/suffixes.txt", "w") do |f|
    suffixes.each do |suf|
        f.puts suf
    end
end
