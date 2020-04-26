require "rubygems"
require "mechanize"
require "nokogiri"
require "csv"
require "down"
require "fileutils"
require "json"

support_urls_consolidated = File.open("./temp/support_urls_consolidated.txt", "r").readlines
support_urls_consolidated = support_urls_consolidated.reject(&:empty?)
support_urls_consolidated = support_urls_consolidated.map {|x| x.chomp}

agent = Mechanize.new

images_array = [] # this array holds all the image names we have seen so far, so we can rename any new images (for example, 2 images on different docs might be named "01.PNG")

namechanges = []

type_to_json_mapping = [["guides", "How-to Guides"], ["explain", "Explainers"], ["tutorials", "Tutorials"]]

json=JSON.parse(File.open("./sidebars.json").read)

rows = CSV.open("./temp/support_docs.csv", { :col_sep => "\t" }).each.to_a
rows.shift
rows.each do |row|
    unless row == []
        namechanges.push [row[2], row[6], row[3]]
    end
end

links=[]
images=[]

i = 0
support_urls_consolidated.each do |url|
    page = agent.get(url)
    body = page.body
    doc = Nokogiri::HTML(body)
    maincontent = doc.css("#docBody")
    l =  maincontent.css("a").map{ |a| a["href"] }
    l.each do |link|
    	links.push link
    end
    ii =  maincontent.css("img").map {|img| img["src"]}
    ii.each do |im|
    	puts im
    	images.push im
    end
end

File.write("./temp/links.txt", links.join("\n"))
File.write("./temp/images.txt", images.join("\n"))