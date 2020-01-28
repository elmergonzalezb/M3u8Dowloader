# _*_ encoding:utf-8 _*_

import re
import os
import gevent
from queue import Queue
from Crypto.Cipher import AES
from gevent import monkey
from gevent.pool import Pool
import time
gevent.monkey.patch_all()

import requests
from urllib.request import urlretrieve

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Mobile Safari/537.36",
    "connection": "close",
    "Origin":"https://hqq.tv",
    "Referer": "https://hqq.tv/player/embed_player.php?vid=TGVhVW1rUUl4YS9RSHdza0I0NE5TQT09&autoplay=no"

}

DOWNLOAD_UEL = os.getcwd()
DOWNLOAD_UEL_T = os.getcwd()

class M3u8Downloader(object):

    def __init__(self,url,filename="default.mp4",server=""):
        """

        :param url: 下载m3u8文件地址
        :param filename: 文件名如."defualt.mp4"
        """
        self.header=''
        self.url = url
        self.server = server
        self.cryptor=None #解密
        self.concurrent_num=8 #默认并发数
        self.filename = filename
        self.haskey=False #是否是加密流串
        self.dowmload_dir = DOWNLOAD_UEL + r"/download/"
        self.download_dir_T = self.dowmload_dir + filename.split(',')[0]

        self.download_path = self.download_dir_T + "//{name}"

        if not os.path.exists(self.dowmload_dir):
            os.mkdir(self.dowmload_dir)
        if not os.path.exists(self.download_dir_T):
            os.mkdir(self.download_dir_T)
        print(self.dowmload_dir)
        print(self.download_dir_T)
        self.pool = Pool()
        self.queue = Queue()
        self.is_running=True
        self.request_num=0 #发出的请求
        self.response_num=0 #回应的请求

    def getVideoTsUrl(self):
        """
        通过url 下载m3u8文件，读取m3u8文件获取.ts文件链接
        :param url: 下载m3u8文件的地址
        :return: yeild :ts文件地址
        """
        all_content=None
        if self.header!='':
            all_content = requests.get(url=self.url,headers=headers).text
        else:
            all_content = requests.get(url=self.url).text
        #  all_content = requests.get(url).text  # 获取M3U8的文件内容
        file_line = all_content.split("\n")  # 读取文件里的每一行
        # 通过判断文件头来确定是否是M3U8文件
        if 'URI="key.key"' in all_content:#解密
            self.parse_decrytor(self.url)
        if file_line[0] != "#EXTM3U":
            raise BaseException(u"非M3U8的链接")
        else:
            unknow = True  # 用来判断是否找到了下载的地址
            for index, line in enumerate(file_line):
                if "EXT" in line:
                    unknow = False
                else:
                    if line != "":
                        pd_url = self.server + line
                        yield pd_url

            if unknow:
                raise BaseException("未找到对应的下载链接")

    def get_url_list(self):
        """拼接url_list"""
        i = 0
        for url in self.getVideoTsUrl():
            item = {
                "url": url,
                "name": "{name}.ts".format(name=str(i).zfill(3))
            }
            self.queue.put(item)
            self.request_num += 1  # 请求数 +1
            i += 1

    def Schedule(self, a, b, c):
        """
        进度条
        :param a:已经下载的数据块
        :param b:数据块的大小
        :param c:远程文件的大小
        :return:
        """
        per = 100.0 * a * b / c
        if per >= 100:
            per = 100
        print("  " + "%.2f%% 已经下载的大小:%ld 文件大小:%ld" % (per, a * b, c) + '\r')

    def parse_decrytor(self,url):
        filename=os.path.basename(url)
        key_url=re.sub(filename,"key,key",url)
        key = requests.get(key_url, headers=headers).text
        self.cryptor=AES.new(key,AES.MODE_CBC,key)
        self.haskey=True

    def parse_url(self,item):
        """
        发送请求，获取响应
        :param item:
        :return:
        """
        url = item["url"]
        name = item["name"]
        filename = self.download_path.format(name=name)
        if not os.path.exists(filename):
            try:
                print("\"" + filename + "\"" + "已经开始下载")
                if self.haskey:
                    r = requests.get(url=url, headers=headers, timeout=10)
                    with open( filename + ".ts", "wb")as f:
                        if self.cryptor:
                            f.write(self.cryptor.decrypt(r.content))
                urlretrieve(url, filename, reporthook=self.Schedule)
                print("\"" + filename + "\"" + "已经下载完成")
            except Exception as e:
                print(e)
                # 没有下载成功再次进入队列
                self.queue.put(url)
                self.request_num += 1  # 请求数 +1

    def _execete_request_content_save(self,*args):
        """进行一次url地址的请求，提取，保存"""
        # 1.发送请求
        print("协程编号:%d" % args)
        while not self.queue.empty():
            url = self.queue.get()
            # 2.获取响应
            self.parse_url(url)
            self.response_num += 1  # 响应数 +1


    # def _call_back(self,temp):
    #     """
    #      # 参数 temp 在此处没有用，但不能去掉
    #     :return:
    #     """
    #     if self.is_running:
    #         self.pool.apply_async(func=self._execete_request_content_save,callback=self._call_back)

    def run(self):
        """
        run
        :return:
        """
        #self.pool.apply_async(self.get_url_list())
        self.get_url_list()
        for i in range(self.concurrent_num):
            self.pool.apply_async(func=self._execete_request_content_save, args=(i,))
        while True:
            time.sleep(0.0001)
            if self.response_num >= self.request_num:
                self.is_running = False
                break



def merge_file(filename):
    path = DOWNLOAD_UEL + r"/download/" + filename.split(".")[0]
    os.chdir(path)
    os.system("(for %a in (*.ts) do @echo file '%a') > list.txt")
    os.system(f"ffmpeg -f concat -safe 0 -i list.txt -c copy {filename}.mp4")
    # os.system('del /Q *.ts')
    # os.system('del /Q list.txt')
    os.system("exit")

def paseStreaming(url, filename='', server=''):
    t1 = time.time()
    server=url.replace(os.path.basename(url),"")
    filename = os.path.basename(url).replace("m3u8", "").split('.')[0]
    qb = M3u8Downloader(url=url,filename=filename, server=server)
    qb.header=headers
    qb.concurrent_num=16 #并发数
    qb.run()
    merge_file(filename)
    print("total cost：", time.time() - t1)


if __name__ == '__main__':
    paseStreaming(url="https://dt53fg.vkcache.com/secip/0/aUKBaxdd4Q9cnfYZX78u5Q/MTQwLjIyNy4xMjYuMTIz/1580202000/hls-vod-s09/flv/api/files/videos/2020/01/07/1578403321op2we.mp4.m3u8")