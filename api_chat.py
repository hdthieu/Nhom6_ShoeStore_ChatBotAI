from fastapi import APIRouter
from pydantic import BaseModel
from chatbot import get_llm
from db_loader import get_all_products, get_summary
from unidecode import unidecode
from deep_translator import GoogleTranslator
import pandas as pd
import re, json

router = APIRouter()
llm = get_llm()
df_products = get_all_products()

category_aliases = {
    "giay chay bo": "Running",
    "chay bo": "Running",
    "running": "Running",
    "giay sneaker": "Lifestyle",
    "giay the thao": "Lifestyle",
    "giay da banh": "Football",
    "giay da bong": "Football",
    "bong da": "Football",
    "giay cho tre em": "Kids",
    "giay tre em": "Kids"
}

class ChatRequest(BaseModel):
    query: str

def preprocess(text):
    return unidecode(str(text)).lower().strip()

def translate_to_en(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

def translate_to_vi(text):
    try:
        return GoogleTranslator(source='auto', target='vi').translate(text)
    except:
        return text

def extract_filter_criteria(query, llm, max_retries=3):
    prompt = f"""
        Bạn là trợ lý bán giày vui vẻ, thân thiện. Người dùng vừa hỏi:
        "{query}"

        Hãy chỉ trả về một chuỗi JSON hợp lệ duy nhất, KHÔNG có giải thích gì thêm, chứa các tiêu chí nếu có:
        - brand (chuỗi)
        - category (chuỗi)
        - min_price (số nguyên)
        - max_price (số nguyên)

        Ví dụ trả lời:
        {{ "category": "giày chạy bộ", "min_price": 100000, "max_price": 1000000 }}

        Nếu không có tiêu chí nào, trả về {{}}

        Lưu ý: Chỉ trả về JSON thôi, đừng trả lời văn bản ở đây.
        """
    for attempt in range(max_retries):
        response = llm.invoke(prompt)
        content = getattr(response, 'content', str(response)).strip()
        content = re.sub(r"^```json\s*|\s*```$", "", content, flags=re.MULTILINE)
        try:
            criteria = json.loads(content)
            print(f"Parsed criteria: {criteria}")
            return criteria
        except json.JSONDecodeError as e:
            print(f"JSON decode error on attempt {attempt + 1}: {e}")
            print("LLM raw content:", content)
            continue
    return {}


def analyze_query_with_llm(query):
    prompt = f"""
Bạn là một AI thông minh, thân thiện, hiểu tiếng Việt.

Người dùng hỏi:
"{query}"

Hãy phân loại câu hỏi này vào đúng nhóm sau (chỉ trả về đúng 1 từ):
- summary → nếu hỏi tổng số sản phẩm, số lượng
- brands → nếu hỏi có bao nhiêu hãng, thương hiệu, nhãn hiệu
- search → nếu tìm kiếm giày theo tiêu chí cụ thể
- advice → nếu người dùng nhờ tư vấn

Trả về đúng 1 từ: summary, brands, search hoặc advice.
"""
    response = llm.invoke(prompt)
    action = response.content.strip().lower()
    print(f"🧠 [analyze_query_with_llm] Query: {query} => Action: {action}")
    return action




def filter_products(df, criteria):
    filtered = df.copy()
    if "brand" in criteria:
        brand = preprocess(criteria["brand"])
        filtered = filtered[filtered["brand"].apply(lambda x: preprocess(x) == brand)]
    if "category" in criteria:
        category_key = preprocess(criteria["category"])
        category_mapped = category_aliases.get(category_key, criteria["category"])
        if category_mapped in df["category"].unique():
            filtered = filtered[filtered["category"] == category_mapped]
        else:
            return pd.DataFrame()
    if "min_price" in criteria:
        filtered = filtered[filtered["price"] >= criteria["min_price"]]
    if "max_price" in criteria:
        filtered = filtered[filtered["price"] <= criteria["max_price"]]
    return filtered
@router.post("/chat")
def chat(req: ChatRequest):
    user_input = req.query
    action = analyze_query_with_llm(user_input)
    print(f"Action: {action}, Query: {user_input}")

    df_products = get_all_products()
    total_products, brands, categories = get_summary()

    if action == "brands" or any(kw in preprocess(user_input) for kw in ["hang", "thuong hieu", "nhan hieu"]):
        reply = f"🏷️ Hi bạn, cửa hàng mình hiện có {len(brands)} thương hiệu giày nổi tiếng nhé: {', '.join(brands)}. Bạn thích hãng nào thì cứ hỏi mình nha!"

    elif action == "summary":
        criteria = extract_filter_criteria(user_input, llm)
        if "min_price" in criteria or "max_price" in criteria:
            filtered = filter_products(df_products, criteria)
            count = len(filtered)
            if count == 0:
                reply = "😢 Không có sản phẩm nào phù hợp với tiêu chí giá bạn đưa ra."
            else:
                preview = filtered.head(3)
                product_list = "\n".join([
                    f"- {row['productName']} ({row['brand']}), Giá: {int(row['price']):,} VNĐ"
                    for _, row in preview.iterrows()
                ])
                reply = f"📊 Có {count} sản phẩm phù hợp với tiêu chí bạn đưa ra. Đây là một vài sản phẩm:\n{product_list}"
        else:
            reply = f"🧾 Cửa hàng có tổng cộng **{total_products}** sản phẩm."

    elif action in ["search", "advice"]:
        criteria = extract_filter_criteria(user_input, llm)
        print(f"Criteria extracted: {criteria}")

        if action == "advice" and ("rẻ nhất" in user_input.lower() or "giá thấp nhất" in user_input.lower()):
            cheapest = df_products.nsmallest(3, "price")
            product_list = "\n".join([
                f"- {row['productName']} ({row['brand']}), Giá: {int(row['price']):,} VNĐ"
                for _, row in cheapest.iterrows()
            ])
            reply = f"💡 Mình thấy đây là 3 đôi giày rẻ nhất trong shop nè, bạn tham khảo thử nhé:\n{product_list}"

        else:
            filtered_products = filter_products(df_products, criteria)
            count = len(filtered_products)

            if count == 0:
                suggestions = ", ".join(categories[:5])
                reply = f"Ôi không, mình không tìm thấy sản phẩm phù hợp với yêu cầu của bạn. Bạn thử xem các danh mục sau nhé: {suggestions}."

            else:
                preview = filtered_products.head(3)
                product_list = "\n".join([
                    f"- {row['productName']} ({row['brand']}), Giá: {int(row['price']):,} VNĐ"
                    for _, row in preview.iterrows()
                ])
                reply = f"✅ Có {count} sản phẩm phù hợp với yêu cầu đó. Đây là một vài gợi ý cho bạn:\n{product_list}\nBạn muốn xem thêm không?"

    else:
        reply = "⚠️ Mình chưa hiểu câu hỏi lắm, bạn có thể nói rõ hơn hoặc hỏi cách khác được không?"

    return {"answer": translate_to_vi(reply)}
