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

support_urls_mappings = File.open("./temp/support_urls_new_title_mappings.txt", "r").readlines
support_urls_mappings = support_urls_mappings.reject(&:empty?)
support_urls_mappings = support_urls_mappings.map {|x| x.chomp}
support_urls_mappings = support_urls_mappings.map{|mapping| mapping.split("\t")}


agent = Mechanize.new

images_array = [] # this array holds all the image names we have seen so far, so we can rename any new images (for example, 2 images on different docs might be named "01.PNG")

namechanges = []

type_to_json_mapping = [["guides", "How-to Guides"], ["explain", "Explainers"], ["tutorials", "Tutorials"]]

json=JSON.parse(File.open("./sidebars.json").read)

rows = CSV.open("./temp/support_docs.csv", { :col_sep => "\t" }).each.to_a
rows.shift

ncrows = CSV.open("./temp/support_urls_old_for_namechanges", { :col_sep => "\t" }).each.to_a
ncrows.shift
ncrows.each do |row|
    unless row == []
        namechanges.push [row[2], row[6], row[3]]
    end
end


i = 0
support_urls_consolidated.each do |url|
    page = agent.get(url)
    body = page.body
    doc = Nokogiri::HTML(body)
    maincontent = doc.css("#docBody")
    links = maincontent.css("a")
    images = maincontent.css("img")

    ######title = doc.css(".entry-title").text
    title = nil
    uri=nil
    support_urls_mappings.each do |mapping|
        uri = mapping[0]
        if (url == uri)
            title = mapping[1]
            break
        else
            title = "TITLE NOT GENERATED"
        end
    end

    todos = []
    
    j=0
    links.each do |link|
        href = link["href"]
        unless href == nil
            namechanges.each do |nc|
                old = nc[0]
                new = nc[1]
                if href.include? old
                    #puts [href, old, new].join("\t")
                    links[j]["href"] = new
                end
            end

            if href.include? "/dev/docs/img/"
                imgName = href.split("/").last
                unless images_array.include? imgName
                    links[j]["href"] = "/docs/img/" + imgName
                    images_array.push imgName
                else
                    imgNameSplit = href.split("/").last.split(".")
                    imgNameSplit[0] += "_#{i}"
                    imgName = imgNameSplit.join(".")
                    links[j]["href"] = "/docs/img/" + imgName
                end

                imgName = href.split("/").last
                tempfile = Down.download(href)
                FileUtils.mv(tempfile.path, "./images/#{imgName}")
                links[j]["href"] = "/docs/img/" + imgName
            elsif href.include? "/dev/docs"
                todos.push "todo: Modify links to old API docs"
            elsif href.include? "/dev/"
                todos.push "todo: Modify links to old Dashboard"
            elsif href.include? "/img/"
                imgName = href.split("/").last
                unless images_array.include? imgName
                    links[j]["href"] = "/docs/img/" + imgName
                    images_array.push imgName
                else
                    imgNameSplit = href.split("/").last.split(".")
                    imgNameSplit[0] += "_#{i}"
                    imgName = imgNameSplit.join(".")
                    links[j]["href"] = "/docs/img/" + imgName
                end
            elsif href.include? "/pricing/"
                links[j]["href"] = "https://diffbot.com" + href
            elsif href.include? "/products/"
                links[j]["href"] = "https://diffbot.com" + href
            elsif href.include? "support.diffbot.com/topics"
                todos.push "todo: Modify link beginning with \"support.diffbot.com/topics\""
            elsif href.start_with? "/"
                links[j]["href"] = "https://diffbot.com" + href
            end
        end
        j += 1
    end
    
    k = 0
    images.each do |img|
        src = img["src"]
        puts src
        imgName = src.split("/").last
        puts imgName
        puts images_array.include? imgName
        unless images_array.include? imgName
            img["src"] = "/img/" + imgName
            puts "src:" + img["src"]
            images_array.push imgName
        else
            imgNameSplit = src.split("/").last.split(".")
            imgNameSplit[0] += "_#{i}"
            imgName = imgNameSplit.join(".")
            images[k]["src"] = "/img/" + imgName
            i += 1
        end
        if src.start_with?("/")
            src = "https://diffbot.com" + src
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
    maincontent.to_html.gsub(/<pre.*?>/, "\n\n```text\n").gsub("</pre>", "\n```\n\n").each_line { |line|
        html_out += line.gsub(/^\s+</, '<')
    }

    html_out = html_out.gsub("```text\n\n", "```text\n").gsub("\n\n```\n", "\n```\n")
    #html_out += maincontent.to_html

    File.write("./docs/#{id}.md", html_out)

    newType = nil
    type_to_json_mapping.each do |t|
        begin
        if pageType.chomp == t[0]
            newType = t[1]
        elsif pageType.chomp == "error"
            newType = "Errors"
        elsif pageType.chomp == "api"
            newType = "API"
        end
        rescue
            puts "URL: " + url + "####################"
            puts url
            puts "URL: " + url + "####################"
            exit
        end
    end

    if newType == "API"
        json["docs-other"]["API"].push id
    elsif newType == "Errors"
        json["docs-errors"]["Errors"].push id
    else
        json["docs"][newType].push id
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