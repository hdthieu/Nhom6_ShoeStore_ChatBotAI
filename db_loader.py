import pyodbc
import pandas as pd

def get_all_products():
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost,1433;"
        "DATABASE=ShoeStore_ProductService;"
        "UID=sa;"
        "PWD=sapassword"
    )
    query = """
    SELECT 
        p.productID, p.productName, p.description, p.price,
        c.name AS category, b.name AS brand
    FROM Product p
    JOIN Category c ON p.categoryID = c.categoryID
    JOIN Brand b ON p.brandID = b.brandID
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_summary():
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost,1433;"
        "DATABASE=ShoeStore_ProductService;"
        "UID=sa;"
        "PWD=sapassword"
    )

    # Tổng sản phẩm
    count_sql = "SELECT COUNT(*) AS cnt FROM Product"
    total_products = pd.read_sql(count_sql, conn).iloc[0]["cnt"]

    # Lấy tất cả thương hiệu, kể cả chưa có sản phẩm
    brands = pd.read_sql("""
        SELECT name FROM Brand
        ORDER BY name
    """, conn)["name"].tolist()

    # Các loại giày (chỉ lấy loại đã có sản phẩm)
    categories_sql = """
        SELECT DISTINCT c.name 
        FROM Category c
        JOIN Product p ON p.categoryID = c.categoryID
    """
    categories = pd.read_sql(categories_sql, conn)["name"].tolist()

    print("Brands loaded:", brands)
    print("Total brands:", len(brands))

    conn.close()
    return total_products, brands, categories
