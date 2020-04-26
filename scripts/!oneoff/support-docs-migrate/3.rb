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

rows = CSV.open("./temp/support_docs.csv").each.to_a
rows.shift
rows.each do |row|
    unless row == []
        namechanges.push [row[2], row[6], row[3]]
    end
end

i = 0
support_urls_consolidated.each do |url|
    page = agent.get(url)
    body = page.body
    doc = Nokogiri::HTML(body)
    maincontent = doc.css(".entry-content")
    links = maincontent.css("a")
    images = maincontent.css("img")

    title = doc.css(".entry-title").text

    todos = []
    
    j=0
    links.each do |link|
        href = link["href"]
        unless href == nil
            namechanges.each do |nc|
                old = nc[0]
                new = nc[1]
                if href.include? old
                    links[j]["href"] = new
                end
            end
            if href.include? "/dev/docs"
                todos.push "todo: Modify links to old API docs"
            elsif href.include? "/dev/"
                todos.push "todo: Modify links to old Dashboard"
            end
        end
        j += 1
    end
    
    k = 0
    images.each do |img|
        src = img["src"]
        imgName = src.split("/").last
        unless images_array.include? imgName
            img["src"] = "/docs/img/" + imgName
            images_array.push imgName
        else
            imgNameSplit = src.split("/").last.split(".")
            imgNameSplit[0] += "_#{i}"
            imgName = imgNameSplit.join(".")
            images[k]["src"] = "/docs/img/" + imgName
            i += 1
        end
        tempfile = Down.download(src)
        FileUtils.mv(tempfile.path, "./images/#{imgName}")
        k += 1
    end

    newPageName = nil
    pageType=nil
    namechanges.each do |nc|
        old = nc[0]
        new = nc[1]
        type = nc[2]
        if url.include? old
            newPageName = new
            pageType = type
        end
    end

    id = newPageName
    sidebar_label = title

    html_out = "---\n"  + "id: #{id}\n" + "title: #{title}\n" + "sidebar_label: #{sidebar_label}\n"
    todos.uniq.each do |td|
        html_out += td + "\n"
    end
    html_out += "---\n\n"
    html_out += maincontent.to_html

    File.write("./docs/#{id}.md", html_out)

    newType = nil
    type_to_json_mapping.each do |t|
        if pageType.chomp == t[0]
            newType = t[1]
        elsif pageType.chomp == "error"
            newType = "Errors"
        end
    end

    unless newType == "Errors"
        json["docs"][newType].push id
    else
        json["docs-errors"]["Errors"].push id
        puts id
    end
end

File.write("./sidebars2.json", json.to_json)

=begin
    
For each link we must check if it is:
1. in the list of all pages.  If so, change link href to NEW_FILENAME
2. an image URL.  If it is, download the image and add to image folder, then update src if needed
2. a link to the old Dashboard.  If so, add a TODO to update links to Dash
4. a link to the old API Docs.  If so, add a TODO to update links to Docs
    
=end