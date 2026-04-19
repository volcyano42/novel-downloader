from nldlder import NovelDownloader, Options

if __name__ == "__main__":
    options: Options = Options().set_mode("api")
    nl = NovelDownloader(options)
    options.set_api_options(key = "")
    url = input("请输入url: ")
    nl.download(url)