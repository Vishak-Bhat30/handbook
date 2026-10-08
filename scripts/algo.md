The task for you is very simple.

1. You can convert the SOP each para into a list so that you can parse easily
2. Convert each para into python verifiers, which can use a small SLM at port 8000 to extract infromation from the conversation / tool call output so far.
3. Based on the output of the verifier I want to block the tool call if the args are wrong or if the tool call is itself wrong and give appropriate feedback so that we can steer the model from there. (interwhen)
4. Once this is done please give me the code to run the interwhen style run on this example.


Make sure that to build the verifiers you only use the SOP, and you can also try to build some kind of completion verifier -- by just using the SLM that we have as an additional extractor. Use it only for extraction, the rest checks should be python based code verifiers.