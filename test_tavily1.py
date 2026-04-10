import os
os.environ["OPENAI_API_KEY"] =""
TAVILY_API_KEY=""
PERPLEXITY_API_KEY=''
from llama_index.tools.tavily_research.base import TavilyToolSpec
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.workflow import Context
from llama_index.core.agent.workflow import ToolCallResult, AgentStream
import asyncio
from llama_index.agent.openai import OpenAIAgent
import requests
import re
import json
import requests
from llama_index.core import Document, PromptTemplate, SummaryIndex
from llama_index.llms.openai import OpenAI
import pandas as pd

Settings.llm = OpenAI(model="gpt-4.1")

def llm_search(query: str):
  """Query a large language model"""
  response = OpenAI(model="gpt-4.1").complete(query)
  return response



async def main_perplexity(query,model):
    def prepare_openai_message_market_size(query,company_name=None,company_info='',industry=''):
        messages=[{
                                "role":"system",
                                "content":f"""You are a star consultant at a leading consulting/ investment research firm (eg. Bain, Mckinsey, BCG etc.) - 15+ years experienced.
Your customers are the private equity funds who rely on your research to help make their investment decisions.
Your job includes (but not limited to) creating different Industry analysis, doing commercial due diligence and financial due diligence on target companies."""
                                
                                },
                            {

                                "role": "user",
                                "content": f"""Question: {query}
Answer:"""

                                        }

                                
                        ]
        return messages
    import requests

    API_URL = "https://api.perplexity.ai/chat/completions"
    API_KEY = PERPLEXITY_API_KEY

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    messages= prepare_openai_message_market_size(query)

    payload = {
        "model": model,
        "messages": messages,
        "web_search_options":{
            "search_context_size": "high"  # Options: "low", "medium", "high"
        }
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    print(response.json())
    result= response.json()
    res=result['choices'][0]['message']['content']
    citations= result.get('citations')

    clean_res=re.sub(r'<think.*?>.*?</think>', '', res, flags=re.DOTALL | re.IGNORECASE)
    return {"Answer":clean_res,"Citations":citations}



async def main_tavily(query):
    tavily_tool = TavilyToolSpec(
    api_key=TAVILY_API_KEY    
    )
    agent = ReActAgent(
        tools=tavily_tool.to_tool_list()+[llm_search],
        llm=OpenAI(model="gpt-4.1"),
        system_prompt="""You are a star consultant at a leading consulting/ investment research firm (eg. Bain, Mckinsey, BCG etc.) - 15+ years experienced.
Your customers are the private equity funds who rely on your research to help make their investment decisions.
Your job includes (but not limited to) creating different Industry analysis, doing commercial due diligence and financial due diligence on target companies.
You have the following tools at your disposal for comprehensive research:
1. Tool for searching information from the internet.
2. Tool for quering a large language model.
Give in-line citations along with the list of citations that are used in your response."""
    )
    
    ctx = Context(agent)

    handler = agent.run(query, ctx=ctx)
    async for ev in handler.stream_events():
        if isinstance(ev, ToolCallResult):
            print(f"\nCall {ev.tool_name} with {ev.tool_kwargs}\nReturned: {ev.tool_output}")
        if isinstance(ev, AgentStream):
            print(f"{ev.delta}", end="", flush=True)

    response = await handler

    #print("\nFinal response:",response)
    return response

async def main_tavily_custom(query):      

    def _tavily_search(query):
        url = "https://api.tavily.com/search"

        payload = {
            "query": query,
            "topic": "general",
            "search_depth": "basic",
            "chunks_per_source": 3,
            "max_results": 10,
            "time_range": None,
            "days": 7,
            "include_answer": False,
            "include_raw_content": True,
            "include_images": False,
            "include_image_descriptions": False,
            "include_domains": [],
            "exclude_domains": []
        }
        headers = {
            "Authorization": TAVILY_API_KEY,
            "Content-Type": "application/json"
        }

        response = requests.request("POST", url, json=payload, headers=headers)
        
        #print(response.text)
        #print(json.loads(response.text))
        return json.loads(response.text)
    
    def _update_prompt_template(summary_engine,summary_generation=False):
        refine_qna_template=(

    "Context information from multiple sources is below\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    """Return a maximum of 25 lines markdown formatted critical analysis for query given below using the given context and not your prior knowledge.
    Please generate concise and direct answers.\n"""
    "Given the information from multiple sources, answer the query in the tone of an investment analyst.\n"
    "Query: {query_str}\n"
    "Answer:" )

    #     refine_summary_template=(

    # "Context information from multiple sources is below\n"
    # "---------------------\n"
    # "{context_str}\n"
    # "---------------------\n"
    # """Return a one page long markdown formatted answer for query given below using the given context and not your prior knowledge.\n"""
    # "Given the information from multiple sources, answer the query in the tone of an credit risk analyst.\n"
    # "Query: {query_str}\n"
    # "Answer:" )
        refine_summary_template=(

    "Context information from multiple sources is below\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    """Return a maximum of one page long markdown formatted answer for query given below using the given context and not your prior knowledge.
    Given the information from multiple sources, answer the query in the tone of a seasoned consulting analyst. Analyse the information from all the provided sources and Return a detailed reponse with citations.
    Please respond by citing the sources in-line using numbers like [1] at their respective positions.
        - Use only the sources (url) given in the metadata of the context for citations.
        - Use only the source which are used to generate the answers
        - Make sure not to create multiple citations for the same source
        - Make sure to return a list of citations at the end of the response.
        - Make sure that the in-line citation number matches with the citations given in the list.
        - do not add hyperlinks\n"""
    "Return 'data not available' if the query cannot be answered based on the given context.\n"
    "Given the information from multiple sources and your prior knowledge, answer the query along with citations in the tone of an investment analyst.\n"
  
    "Query: {query_str}\n"
    "Answer:" )       
    

        if summary_generation:
            refine_prompt = PromptTemplate(refine_summary_template)
        else:
            refine_prompt = PromptTemplate(refine_qna_template)
        summary_engine.update_prompts(
            {"response_synthesizer:summary_template": refine_prompt}
        )

        return summary_engine

    def _create_query_engine(documents):
        #search_results = tavily_search(query)
        #documents= search_results['results']
        #print(documents)
        document_nodes=[]
        for doc in documents:
            extra_info = {
                    "url": doc.get("url", None),
                    "title": doc.get("title",None)
                }
            print(extra_info)
            document_nodes.append(Document(text=doc['content'],extra_info=extra_info))
        
        summary_index = SummaryIndex(nodes=document_nodes)
        llm_client=OpenAI(temperature=0, model='gpt-4.1')
        summary_engine = summary_index.as_query_engine(
                    response_mode="tree_summarize",
                    llm=llm_client                
                )
        #summary_engine=update_prompt_template(summary_engine,summary_generation=True)    
        return summary_engine
    
    search_results1 = _tavily_search(query)
    
    summary_engine= _create_query_engine(search_results1['results'])

    llm_client=OpenAI(temperature=1.0, model='gpt-4.1')
    summary_engine.llm=llm_client
    summary_engine=_update_prompt_template(summary_engine,summary_generation=True)    
    response = summary_engine.query(query + '- Make sure to create a table of data sources (url), year/ period, market size, CAGR, Region, Segments included\n- make sure to return the citations. Think step by step to do a bottom up approach.' ) 
    
    return str(response)


async def main():
    industry = ["Fitness and Gym lockers","Fitness and Gym flooring"]
    geography= "United States"
    Responses={}
    for ind in industry:
        query=f"what is the market size of the {ind} industry in: {geography} ? Estimate the size using multiple sources following a bottom up approach."
        query.format(industry=industry,geography=geography)
        # perplexity_task = main_perplexity(query,model="sonar-pro")
        # perplexity_task_reasoning = main_perplexity(query,model="sonar-reasoning-pro")
        # tavily_task = main_tavily(query)
        tavily_custom_task= await main_tavily_custom(query)
        #gemini_task = main_gemini(query)
        #answer_perplexity,answer_perplexity_reasoning,answer_tavily,answer_tavily_custom=await asyncio.gather(perplexity_task,perplexity_task_reasoning,tavily_task,tavily_custom_task)
        #answer_perplexity,answer_tavily,answer_gemini =await asyncio.gather(perplexity_task,tavily_task,gemini_task)

        #print(f"\nPerplexity Response:\n{answer_perplexity}")
        #print(f"\nTavily Response:\n{answer_tavily}")
        # Responses[ind]={"perplexity":answer_perplexity,
        #                 "perplexity_reasoning":answer_perplexity_reasoning,
        #                  "react_tavily":str(answer_tavily),
        #                  "custom_tavily":answer_tavily_custom}
        Responses[ind]={"custom_tavily":tavily_custom_task}
    
    df=pd.DataFrame().from_records(Responses)
    df1=df.T
    df1.to_csv('market_size_test.csv')        

    return Responses


if __name__=="""__main__""":
    
    asyncio.run(main())


  