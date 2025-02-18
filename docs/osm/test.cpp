#include <iostream>
#include <sstream>
#include <map>
#include <vector>
#include "tinyxml/tinyxml.h"
#include "jsoncpp/json/json.h"
#include <emscripten/bind.h> // 这个include在ide里面有可能会报错但是可以正常编译

using namespace emscripten;

using namespace std;

// 改为了类似json的格式方便数据转换
Json::Value nodes;
Json::Value ways;

// 初始化，和上一版内容基本相同
void load()
{
    TiXmlDocument tinyXmlDoc("map");
    tinyXmlDoc.LoadFile();
    TiXmlElement *root = tinyXmlDoc.RootElement();

    TiXmlElement *nodeElement = root->FirstChildElement("node");
    for (; nodeElement; nodeElement = nodeElement->NextSiblingElement("node"))
    {
        Json::Value node;
        node["id"] = nodeElement->Attribute("id");
        node["lon"] = nodeElement->Attribute("lon");
        node["lat"] = nodeElement->Attribute("lat");
        nodes[nodeElement->Attribute("id")] = node;
    }
    TiXmlElement *wayElement = root->FirstChildElement("way");
    for (; wayElement; wayElement = wayElement->NextSiblingElement("way"))
    {
        Json::Value way;
        way["id"] = wayElement->Attribute("id");

        Json::Value wayNodes;
        TiXmlElement *childNode = wayElement->FirstChildElement("nd");
        for (; childNode; childNode = childNode->NextSiblingElement("nd"))
        {
            string ref = childNode->Attribute("ref");
            wayNodes.append(nodes[ref]);
        }
        way["nodes"] = wayNodes;

        Json::Value wayTags;
        TiXmlElement *childTag = wayElement->FirstChildElement("tag");
        for (; childTag; childTag = childTag->NextSiblingElement("tag"))
        {
            string name = childTag->Attribute("k");
            string value = childTag->Attribute("v");
            wayTags[name] = value;
        }
        way["tags"] = wayTags;

        ways[wayElement->Attribute("id")] = way;
    }
}

// 这两个函数返回的是json格式的数据
string getNodes()
{
    Json::StreamWriterBuilder builder;
    string s = Json::writeString(builder, nodes);
    return s;
}

string getWays()
{
    Json::StreamWriterBuilder builder;
    string s = Json::writeString(builder, ways);
    return s;
}

// emscripten对于c++代码的处理，为了让前端能调用这些函数
EMSCRIPTEN_BINDINGS()
{
    emscripten::function("load", &load);
    emscripten::function("getNodes", &getNodes);
    emscripten::function("getWays", &getWays);
}