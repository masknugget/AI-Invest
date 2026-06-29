from infra_structure.models.dao.industry_obj import IndustryQuery

from infra_structure.data_engine.visitor.file_visitor import FileVisitor


file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()

df_1 = file_visitor.random_one()
df_2 = file_visitor.random_one()
df_3 = file_visitor.random_one()


industry_query = IndustryQuery()


code_1 = df_1.code.iloc[0]
code_2 = df_2.code.iloc[0]
code_3 = df_3.code.iloc[0]


industry_name_1 = industry_query.query(code_1)
industry_name_2 = industry_query.query(code_2)
industry_name_3 = industry_query.query(code_3)


weights = [0.3, 0.3, 0.3]

