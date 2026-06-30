"""
应用配置类
用于集中管理应用配置项
"""
import os

class Config:
    MODE = 'DEV'
    user = "AISCDHKUA1_APPUSER"
    host = "amh-dev-wpdocdb01-hk.wealth-platform-amh.dev.aws.cloud.hsbc"
    db = "AISCD_AMH_UAT"
    pwd = "AISCDHKUA1_APPUSER.123"
    ca = r"C:\swdtools\cert\global-bundle.pem"
    # ca = r"/app/app/config/global-bundle.pem"

    # 大模型
    MODEL = "Gemini-2.5-pro"
    USER_ID = "UC0003983"
    SERVICE_ACCOUNT = "HK-SVCAT-IPO-DEV"
    PASSWORD = "75F1-f80dCD4B2"

    BASE_URL_SDK = "https://gaip-api-uat.hsbc-12152296-qaipuat-dev.dev.gcp.cloud.hk.hsbc/etiv-ssvc-aigateway-ea-chatcompletion-uat-internal-proxy/v1/api/v1"
    BASE_URL_API = "https://gaip-api-uat.hsbc-12152296-qaipuat-dev.dev.gcp.cloud.hk.hsbc/etiv-ssvc-aigateway-ea-chatcompletion-uat-internal-proxy/v1/api/v1"
    IB2B_DSP_URL = "https://cmb-ib2b-dsp-pprod-ap.hk.hsbc:8443/dsp/rest-sts/DSP_IB2B/iB2B_tokenTranslator?_action=translate"

    # BM25 索引持久化目录
    bm25_persist_directory = os.getenv("BM25_PERSIST_DIRECTORY", r"C:\projects\PycharmProjects\AlphaFlow\data\bm25")

    # BM25 默认集合名称
    bm25_default_collection = os.getenv("BM25_DEFAULT_COLLECTION", "stock_basic")

    # BM25 算法参数
    bm25_k1 = float(os.getenv("BM25_K1", "1.5"))      # 词频饱和度参数
    bm25_b = float(os.getenv("BM25_B", "0.75"))       # 文档长度归一化参数
    bm25_delta = float(os.getenv("BM25_DELTA", "0.5")) # BM25+ delta 参数

    # BM25 计算方法: robertson, lucene, atire, bm25l, bm25+
    bm25_method = os.getenv("BM25_METHOD", "lucene")


# class Config:
#     MODE = 'PRODUCT'
#     user = "AISCDHKUA1_APPUSER"
#     pwd = "AISCDHKUA1_APPUSER.123"
#     host = "wealth-wpamh-ap-east-1-dev-docdb01.cluster-cn9pdf2888wz.ap-east-1.docdb.amazonaws.com"
#     db = "AISCD_AMH_UAT"
#     ca = "/app/app/config/global-bundle.pem"
#
#     MODEL = "Gemini-2.5-pro"
#     USER_ID = "UC0003983"
#     SERVICE_ACCOUNT = "HK-SVCAT-IPO-DEV"
#     PASSWORD = "75F1-f80dCD4B2"
#
#     BASE_URL_SDK = "https://gaip-api-uat.hsbc-12152296-qaipuat-dev.dev.gcp.cloud.hk.hsbc:5443/etiv-ssvc-aigateway-ea-chatcompletion-uat-internal-proxy/v1/api/v1"
#     BASE_URL_API = "https://gaip-api-uat.hsbc-12152296-qaipuat-dev.dev.gcp.cloud.hk.hsbc:5443/etiv-ssvc-aigateway-ea-chatcompletion-uat-internal-proxy/v1/api/v1"
#     IB2B_DSP_URL = "https://cmb-ib2b-dsp-pprod-ap.hk.hsbc:8443/dsp/rest-sts/DSP_IB2B/iB2B_tokenTranslator?_action=translate"
#
#     # BM25 索引持久化目录
#     bm25_persist_directory = os.getenv("BM25_PERSIST_DIRECTORY", r"G:\projects\gitdata\AI-Invest\data\bm25")
#
#     # BM25 默认集合名称
#     bm25_default_collection = os.getenv("BM25_DEFAULT_COLLECTION", "stock_basic")
#
#     # BM25 算法参数
#     bm25_k1 = float(os.getenv("BM25_K1", "1.5"))      # 词频饱和度参数
#     bm25_b = float(os.getenv("BM25_B", "0.75"))       # 文档长度归一化参数
#     bm25_delta = float(os.getenv("BM25_DELTA", "0.5")) # BM25+ delta 参数
#
#     # BM25 计算方法: robertson, lucene, atire, bm25l, bm25+
#     bm25_method = os.getenv("BM25_METHOD", "lucene")