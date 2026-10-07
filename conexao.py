import psycopg

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="engenharia2",
    user="postgres",
    password="postgres"
)

print("Conectado ao PostgreSQL com sucesso!")

cursor = conn.cursor()

cursor.execute("SELECT * FROM peca_roupa")

#pega todas as linhas que o select retornou
tabelas = cursor.fetchall()

#pega tudo que retornou na tabela peco_roupa e imprime
for tabela in tabelas:
    print(tabela)

cursor.close()
conn.close()